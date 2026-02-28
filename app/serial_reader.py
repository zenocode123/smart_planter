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
        # 初始資料全部設為 None
        self.data: Dict[str, Optional[float]] = {
            "temp": None, 
            "hum": None, 
            "moisture": None, 
            "lux": None
        }
        self.is_running = False

    async def run(self):
        """背景任務：持續讀取 Serial 數據"""
        self.is_running = True
        while self.is_running:
            try:
                # timeout 設為 0.1 配合 asyncio.sleep 達成非阻塞
                with serial.Serial(self.port, self.baud, timeout=0.1) as ser:
                    print(f"✅ Serial 已連線: {self.port}")
                    while self.is_running:
                        if ser.in_waiting > 0:
                            try:
                                line = ser.readline().decode('utf-8', errors='ignore').strip()
                                if line.startswith('{'):
                                    new_data = json.loads(line)
                                    self.data.update(new_data)
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                continue 
                        # 讓出控制權給其他異步任務
                        await asyncio.sleep(0.05) 
            except Exception as e:
                print(f"❌ Serial 連線失敗: {e}，5秒後重試...")
                await asyncio.sleep(5)

    def stop(self):
        self.is_running = False

    def get_data(self) -> Dict[str, Any]:
        return self.data

# 單例物件
reader = ESP32Reader()
