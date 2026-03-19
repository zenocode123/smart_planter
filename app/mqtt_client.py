import json
import asyncio
import os
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from typing import Dict, Any, Optional

load_dotenv()

class MQTTPlanterClient:
    def __init__(self):
        # 從環境變數讀取配置，意圖：保持靈活性，支援不同環境部署
        self.broker = os.getenv("MQTT_BROKER", "127.0.0.1")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.keepalive = int(os.getenv("MQTT_KEEPALIVE", "60"))
        
        # 快取感測器數據，意圖：讓前端可以隨時讀取最新狀態，而不需等待下一次發布
        self.data: Dict[str, Any] = {
            "temp": None, 
            "hum": None, 
            "moisture": None, 
            "lux": None,
            "watering": False,
            "status": "disconnected"
        }
        self.is_running = False
        self._client: Optional[mqtt.Client] = None
        self._loop_task: Optional[asyncio.Task] = None

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """MQTT 連線成功回調。理由：連線成功後必須立即訂閱感測器數據 Topic。"""
        if rc == 0:
            print(f"✅ MQTT 已連線至 Broker: {self.broker}")
            self.data["status"] = "connected"
            # 訂閱來自 ESP32 的感測器數據
            client.subscribe("smart_planter/sensors")
        else:
            print(f"❌ MQTT 連線失敗，代碼: {rc}")
            self.data["status"] = "disconnected"

    def _on_message(self, client, userdata, msg):
        """處理接收到的 MQTT 訊息。理由：將 JSON 負載解析並更新本地快取。"""
        try:
            payload = msg.payload.decode()
            new_data = json.loads(payload)
            # 更新本地數據快取，確保與 ESP32 狀態同步
            self.data.update(new_data)
            self.data["status"] = "connected"
        except Exception as e:
            print(f"❌ MQTT 訊息解析失敗: {e}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """連線中斷回調。理由：及時反應狀態，並清理快取數據避免顯示過期資訊。"""
        print("⚠️ MQTT 連線已斷開")
        self.data["status"] = "disconnected"
        # 斷線時，感測器數據設為 None 代表不可用
        self.data.update({
            "temp": None, 
            "hum": None, 
            "moisture": None, 
            "lux": None,
            "watering": False
        })

    async def run(self):
        """
        啟動 MQTT 客戶端背景任務。
        設計意圖：使用 paho-mqtt 的異步迴圈，確保與 FastAPI 的 asyncio 核心相容。
        """
        self.is_running = True
        
        # 使用最新的 Client 類別建構子 (paho-mqtt 2.0+)
        self._client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        try:
            # 異步非阻塞連線
            self._client.connect(self.broker, self.port, self.keepalive)
            
            # 啟動 paho-mqtt 的網路迴圈
            # 注意：paho-mqtt 原生 loop 是阻塞或執行緒式的，
            # 在 FastAPI 中，我們使用 loop_start() 配合 is_running 監控。
            self._client.loop_start()
            
            while self.is_running:
                await asyncio.sleep(1) # 僅需維持背景任務不退出
                
        except Exception as e:
            print(f"❌ MQTT 執行期錯誤: {e}")
        finally:
            self.stop()

    async def send_command(self, action: str, params: dict = None) -> bool:
        """
        發送指令至 ESP32。
        設計意圖：將動作封裝為 JSON 並發布至 command Topic，由 ESP32 訂閱執行。
        """
        if self._client and self.data["status"] == "connected":
            try:
                cmd = {"action": action}
                if params:
                    cmd.update(params)
                
                payload = json.dumps(cmd)
                # 發布至指令主題
                result = self._client.publish("smart_planter/commands", payload)
                result.wait_for_publish() # 確保指令已送出
                
                # HTMX 優化：如果是澆水動作，前端預期立即看到狀態改變
                if action == "water":
                    self.data["watering"] = True

                print(f"🚀 [MQTT] 指令已發布: {cmd}")
                return True
            except Exception as e:
                print(f"❌ [MQTT] 指令發送失敗: {e}")
        else:
            print("⚠️ [MQTT] 未連線，無法發送指令")
        return False

    def stop(self):
        """安全停止 MQTT 連線與迴圈。"""
        self.is_running = False
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None

    def get_data(self) -> Dict[str, Any]:
        """供路由器獲取當前感測器快取數據。"""
        return self.data

# 單例模式提供給整個 FastAPI 應用程式使用
mqtt_client = MQTTPlanterClient()
reader = mqtt_client # 別名，方便平滑替換 serial_reader
