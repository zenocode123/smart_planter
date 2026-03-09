import json
import asyncio
import os
import serial
from dotenv import load_dotenv
from typing import Dict, Any, Optional

load_dotenv()

class ESP32Reader:
    def __init__(self):
        # 從環境變數讀取配置
        self.port = os.getenv("SERIAL_PORT")
        self.baud = int(os.getenv("BAUD_RATE"))
        # 初始資料
        self.data: Dict[str, Any] = {
            "temp": None, 
            "hum": None, 
            "moisture": None, 
            "lux": None,
            "watering": False,
            "status": "disconnected"
        }
        self.is_running = False
        self._serial: Optional[serial.Serial] = None
        self._lock = asyncio.Lock()  # 新增鎖，保護 Serial 埠存取

    async def run(self):
        """背景任務：持續讀取 Serial 數據"""
        self.is_running = True
        while self.is_running:
            try:
                # 建立連線
                ser = serial.Serial(self.port, self.baud, timeout=0.1)
                self._serial = ser
                print(f"✅ Serial 已連線: {self.port}")
                self.data["status"] = "connected"
                
                while self.is_running:
                    async with self._lock:
                        if self._serial and self._serial.in_waiting > 0:
                            try:
                                line = self._serial.readline().decode('utf-8', errors='ignore').strip()
                                if line.startswith('{'):
                                    new_data = json.loads(line)
                                    self.data.update(new_data)
                                    self.data["status"] = "connected"
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                continue 
                    await asyncio.sleep(0.05) 
                
                # 結束時關閉
                if self._serial:
                    self._serial.close()
                    self._serial = None
            except Exception as e:
                self._serial = None
                # 斷線時重置數據
                self.data.update({
                    "temp": None, 
                    "hum": None, 
                    "moisture": None, 
                    "lux": None,
                    "watering": False,
                    "status": "disconnected"
                })
                print(f"❌ Serial 連線失敗: {e}，5秒後重試...")
                await asyncio.sleep(5)

    async def send_command(self, action: str, params: dict = None) -> bool:
        """向 ESP32 發送 JSON 指令 (使用 Lock 確保異步安全)"""
        async with self._lock:
            if self._serial and self._serial.is_open:
                try:
                    cmd = {"action": action}
                    if params:
                        cmd.update(params)
                    
                    payload = (json.dumps(cmd) + "\n").encode('utf-8')
                    self._serial.write(payload)
                    self._serial.flush()
                    
                    # 小技巧：如果成功發送澆水指令，先手動將狀態設為 True 
                    # 這樣網頁能立即刷出彈窗，而不用等 ESP32 下次回報
                    if action == "water":
                        self.data["watering"] = True

                    print(f"🚀 [SERIAL] 指令已成功送出: {cmd}")
                    return True
                except Exception as e:
                    print(f"❌ [SERIAL] 指令發送失敗: {e}")
            else:
                print("⚠️ [SERIAL] 無法發送指令：序列埠未連線或已關閉")
        return False

    def stop(self):
        self.is_running = False

    def get_data(self) -> Dict[str, Any]:
        return self.data

# 單例物件
reader = ESP32Reader()
