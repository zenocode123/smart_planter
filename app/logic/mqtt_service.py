import asyncio
import json
import logging
from paho.mqtt import client as mqtt_client
from app.models import Plant, PlantLog
from app.logic.security import load_dotenv
import os

load_dotenv()

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MQTTService")


class MQTTService:
    def __init__(self):
        self.broker = os.getenv("MQTT_BROKER_HOST")
        self.port = int(os.getenv("MQTT_BROKER_PORT", 1883))
        self.client_id = f"smart-planter-server"
        self.client = None
        self.loop = None
        self.is_running = False
        self.latest_water_empty = {}
        self.latest_watering = {}  # 快取各裝置澆水中狀態
        self.latest_update_time = {} # 快取各裝置最新更新時間戳記

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("✅ Connected to MQTT Broker!")
            # 訂閱所有植物的感測器主題：planter/+/sensor
            # '+' 是萬用字元，代表 mqtt_topic_id
            client.subscribe("planter/+/sensor")
        else:
            logger.error(f"Failed to connect, return code {rc}")

    def on_message(self, client, userdata, msg):
        # 接收到訊息的非同步處理包裝
        payload = msg.payload.decode()
        topic = msg.topic
        # 建立一個 Task 來處理資料庫操作
        asyncio.create_task(self.handle_payload(topic, payload))

    async def handle_payload(self, topic: str, payload: str):
        try:
            # 解析 Topic 獲取 mqtt_topic_id
            # 預期格式：planter/p001/sensor
            parts = topic.split("/")
            if len(parts) < 3:
                return
            mqtt_id = parts[1]

            # 解析 JSON 數據
            data = json.loads(payload)
            logger.info(f"📩 MQTT Received from {mqtt_id}: {data}")

            # 尋找對應的植物紀錄
            plant = await Plant.get_or_none(mqtt_topic_id=mqtt_id)
            if not plant:
                logger.warning(f"⚠️ Unknown plant ID: {mqtt_id}")
                return

            # 快取最新的狀態與更新時間
            import time
            self.latest_water_empty[plant.id] = data.get("water_empty", False)
            self.latest_watering[plant.id] = data.get("watering", False)
            self.latest_update_time[plant.id] = time.time()

            # 存入資料庫
            await PlantLog.create(
                plant=plant,
                temperature=data.get("temp"),
                humidity=data.get("hum"),
                soil_moisture=data.get("soil"),
                lux=data.get("lux"),
            )
            # logger.info(f"💾 Saved log for {plant.nickname}")

        except Exception as e:
            logger.error(f"❌ Error handling MQTT payload: {e}")

    async def run(self):
        self.client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        logger.info(f"🔗 Attempting to connect to {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port)

        self.is_running = True
        # 雖然 paho-mqtt 有 loop_start，但在 FastAPI 中，我們需要整合進 asyncio loop
        while self.is_running:
            self.client.loop(timeout=1.0)
            await asyncio.sleep(0.1)

    def stop(self):
        self.is_running = False
        if self.client:
            self.client.disconnect()
            logger.info("🔌 MQTT Disconnected.")


# 全域單例
mqtt_service = MQTTService()
