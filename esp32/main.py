from machine import Pin, ADC, I2C, deepsleep
import time
import json
from dht import DHT22
from umqtt.simple import MQTTClient
import mdns_resolver
import sm
from bh1750 import BH1750
from oled import OledDisplay
from relay import WaterRelay

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
conf = sm.config()
dht_sensor = DHT22(Pin(25))
soil_sensor = ADC(Pin(26))
light_sensor = BH1750(i2c)
oled = OledDisplay(i2c=i2c)
water_relay = WaterRelay(27)

is_watering = False
water_end_tick = 0

# 載入設定
with open('network_config.json', 'r') as f:
    config = json.load(f)

MQTT_BROKER = config.get('MQTT_BROKER')
CLIENT_ID = config.get('CLIENT_ID')
TOPIC_SENSOR = config.get('TOPIC_SENSOR').encode()
TOPIC_CMD = config.get('TOPIC_CMD').encode()
# 電源模式：預設為 usb
POWER_MODE = config.get('POWER_MODE', 'usb').lower()

# 建立計時變數
last_sensor_read = 0
sensor_interval = 60000  # 每 60 秒讀一次感測器 (降頻保護伺服器)
last_display_mode = None 
emotion_end_tick = 0  # OLED 表情維持的計時器
current_emotion = None

print("ESP32 Ready. Connecting to MQTT and sending data in JSON format...")

# MQTT 回呼函數
def sub_cb(topic, msg):
    global is_watering, water_end_tick, t, h, m, r, l
    global emotion_end_tick, current_emotion, last_display_mode
    print("Received CMD on {}: {}".format(topic, msg))
    try:
        cmd = json.loads(msg)
        
        # 1. 解析澆水指令
        if cmd.get("action") == "water":
            is_watering = True
            # duration 支援小數點
            sec = float(cmd.get("duration", cmd.get("seconds", 3)))
            water_relay.on()
            water_end_tick = time.ticks_add(time.ticks_ms(), int(sec * 1000))
            
            # 準備澆水畫面
            current_emotion = "watering"
            emotion_end_tick = time.ticks_add(time.ticks_ms(), 10000) # 顯示 10 秒
            last_display_mode = None
            
            # 指令確認後立即回報
            send_data(t, h, m, r, l, is_watering)
            
        # 2. 解析情緒指令
        if cmd.get("emotion"):
            current_emotion = cmd.get("emotion")
            emotion_end_tick = time.ticks_add(time.ticks_ms(), 10000) # 顯示 10 秒
            last_display_mode = None
            
    except Exception as e:
        print("MQTT parse error:", e)

# 建立與連接 MQTT 客戶端
try:
    broker_ip = MQTT_BROKER
    if type(MQTT_BROKER) == str and MQTT_BROKER.endswith('.local'):
        print(f"Resolving mDNS for {MQTT_BROKER}...")
        resolved_ip = mdns_resolver.resolve_mdns(MQTT_BROKER)
        if resolved_ip:
            print(f"✅ Resolved to IP: {resolved_ip}")
            broker_ip = resolved_ip
        else:
            print(f"❌ Failed to resolve {MQTT_BROKER}. Connection may fail.")

    client = MQTTClient(CLIENT_ID, broker_ip)
    client.set_callback(sub_cb)
    client.connect()
    client.subscribe(TOPIC_CMD)
    print("Connected to MQTT Broker!")
except Exception as e:
    print("Failed to connect to MQTT broker:", e)
    # 若連線失敗，可視需求加入重試或重機邏輯

def send_data(t, h, m, r, l, watering):
    data = {
        "temp": t,
        "hum": h,         # 對應後端 data.get("hum")
        "soil": m,        # 對應後端 data.get("soil")
        "moisture_raw": r,
        "lux": l,
        "watering": watering
    }
    payload = json.dumps(data)
    try:
        client.publish(TOPIC_SENSOR, payload)
        print("Published:", payload)
    except Exception as e:
        print("MQTT Publish Error:", e)

# 預設感測器初始值
t = h = m = r = l = 0

# --- 雙電源模式防呆邏輯 ---
if POWER_MODE == "battery":
    print("🔋 [Battery Mode] 讀取一次數據後進入深度睡眠...")
    try:
        dht_sensor.measure()
        t = round(dht_sensor.temperature(), 1)
        h = round(dht_sensor.humidity(), 1)
    except:
        pass
    m, r = sm.read(soil_sensor, conf.get('calibrationAir'), conf.get('calibrationWater'))
    l = int(light_sensor.lux)
    
    # 傳一次就跑
    send_data(t, h, m, r, l, False)
    
    # 關閉螢幕與連線
    oled.clear()
    client.disconnect()
    print("進入 Deepsleep，預計 1 小時後甦醒...")
    deepsleep(3600000) # 睡 3600 秒 (1小時)

print("🔌 [USB Mode] 進入電子雞常時待機模式")
while True:
    try:
        current_tick = time.ticks_ms()
        
        # --- 1. 灑水邏輯 ---
        if is_watering:
            if time.ticks_diff(water_end_tick, current_tick) <= 0:
                water_relay.off()
                is_watering = False
                # 狀態改變後立即回報
                send_data(t, h, m, r, l, is_watering)
        
        # --- 2. 非阻塞感測器讀取 ---
        if time.ticks_diff(current_tick, last_sensor_read) > sensor_interval:
            try:
                dht_sensor.measure()
                t = round(dht_sensor.temperature(), 1)
                h = round(dht_sensor.humidity(), 1)
            except:
                pass # 忽略單次讀取失敗
            
            m, r = sm.read(soil_sensor, conf.get('calibrationAir'), conf.get('calibrationWater'))
            l = int(light_sensor.lux)
            
            # 定期發送數據
            send_data(t, h, m, r, l, is_watering)
            
            # 根據是否在情緒展示期間決定顯示內容
            if time.ticks_diff(emotion_end_tick, current_tick) > 0:
                pass # 表情顯示中，暫不顯示感測器數值
            elif not is_watering:
                oled.clear()
                oled.show_text(f"Temp: {t:>5} C", 0, 0)
                oled.show_text(f"Hum:  {h:>5} %", 0, 16)
                oled.show_text(f"Soil: {m:>5} %", 0, 32)
                oled.show_text(f"Lux:  {l:>5} lx", 0, 48)
                last_display_mode = "info"
            
            last_sensor_read = current_tick
            
        # --- 3. 動態表情與狀態顯示 ---
        if time.ticks_diff(emotion_end_tick, current_tick) > 0:
            if last_display_mode != current_emotion:
                oled.clear()
                if current_emotion == "happy":
                    oled.show_center("^       ^", 16)
                    oled.show_center("( O )", 32)
                    oled.show_center("FULL & HAPPY!", 50)
                elif current_emotion == "thirsty":
                    oled.show_center("T       T", 16)
                    oled.show_center("( _ )", 32)
                    oled.show_center("DRY...", 50)
                elif current_emotion == "watering":
                    oled.show_center("o       o", 16)
                    oled.show_center("~ ~ ~ ~", 32)
                    oled.show_center("WATERING...", 50)
                else:
                    oled.show_center("-       -", 16)
                    oled.show_center("z Z z", 32)
                    oled.show_center("SLEEPING.", 50)
                last_display_mode = current_emotion
        elif not is_watering and last_display_mode != "off" and time.ticks_diff(current_tick, last_sensor_read) > 10000:
            # 每 10 秒後無情緒顯示則關閉螢幕省電
            oled.clear()
            last_display_mode = "off"
            
        # --- 4. 指令解析 (MQTT 回呼) ---
        try:
            client.check_msg()
        except Exception as e:
            print("MQTT Check Msg Error:", e)
                
        time.sleep_ms(50) # 提高反應速度
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        time.sleep(2)
