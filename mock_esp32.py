import paho.mqtt.client as mqtt
import json
import time
import random

# MQTT Broker 設定 (請與 .env 一致)
BROKER = "127.0.0.1"
PORT = 1883
TOPIC_SENSORS = "smart_planter/sensors"
TOPIC_COMMANDS = "smart_planter/commands"

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"✅ Mock ESP32 已連線至 Broker: {BROKER}")
    # 模擬 ESP32 訂閱指令主題
    client.subscribe(TOPIC_COMMANDS)

def on_message(client, userdata, msg):
    """模擬收到指令後的反應"""
    try:
        cmd = json.loads(msg.payload.decode())
        print(f"📩 [MOCK] 收到指令: {cmd}")
        if cmd.get("action") == "water":
            print("💧 [MOCK] 開始執行模擬澆水...")
            # 立即回報正在澆水狀態
            report_status(watering=True)
            time.sleep(cmd.get("seconds", 3))
            print("✅ [MOCK] 結束模擬澆水")
            report_status(watering=False)
    except Exception as e:
        print(f"❌ 指令解析錯誤: {e}")

def report_status(watering=False):
    """模擬發送感測器數據"""
    data = {
        "temp": round(random.uniform(20, 30), 1),
        "hum": round(random.uniform(40, 80), 1),
        "moisture": round(random.uniform(30, 90), 1),
        "lux": random.randint(100, 1000),
        "watering": watering
    }
    payload = json.dumps(data)
    client.publish(TOPIC_SENSORS, payload)
    print(f"📤 [MOCK] 已發布數據: {payload}")

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    
    print("🚀 Mock ESP32 啟動中，每 5 秒發送一次數據...")
    while True:
        report_status(watering=False)
        time.sleep(5)
except KeyboardInterrupt:
    print("🛑 Mock ESP32 已停止")
    client.loop_stop()
    client.disconnect()
except Exception as e:
    print(f"❌ 錯誤: {e}")
