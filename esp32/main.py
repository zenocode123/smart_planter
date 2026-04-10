from machine import Pin, ADC, I2C, deepsleep
import time
import json
from dht import DHT11
from umqtt.simple import MQTTClient
import mdns_resolver
import sm
from bh1750 import BH1750
from oled import OledDisplay
from relay import WaterRelay

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
conf = sm.config()
dht_sensor = DHT11(Pin(25))
soil_sensor = ADC(Pin(32))
try:
    light_sensor = BH1750(i2c)
except Exception as e:
    print("Warning: BH1750 未連接或初始化失敗", e)
    light_sensor = None

try:
    oled = OledDisplay(i2c=i2c)
except Exception as e:
    print("Warning: OLED 未連接或初始化失敗", e)
    oled = None

try:
    water_relay = WaterRelay(27, inverted=True, open_drain=True)
except Exception as e:
    print("Warning: 繼電器初始化失敗", e)
    water_relay = None

try:
    water_sensor = Pin(33, Pin.IN, Pin.PULL_UP)
except Exception as e:
    print("Warning: 水位感測器初始化失敗", e)
    water_sensor = None

is_watering = False
water_end_tick = 0

# 載入設定
with open("network_config.json", "r") as f:
    config = json.load(f)

MQTT_BROKER = config.get("MQTT_BROKER")
CLIENT_ID = config.get("CLIENT_ID")
TOPIC_SENSOR = config.get("TOPIC_SENSOR").encode()
TOPIC_CMD = config.get("TOPIC_CMD").encode()
# 電源模式：預設為 usb
POWER_MODE = config.get("POWER_MODE", "usb").lower()

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
            if water_relay:
                water_relay.on()
            water_end_tick = time.ticks_add(time.ticks_ms(), int(sec * 1000))

            # 準備澆水畫面
            current_emotion = "watering"
            emotion_end_tick = time.ticks_add(time.ticks_ms(), 10000)  # 顯示 10 秒
            last_display_mode = None

            # 指令確認後立即回報
            send_data(t, h, m, r, l, is_watering, w_empty)

        # 2. 解析情緒指令
        if cmd.get("emotion"):
            current_emotion = cmd.get("emotion")
            emotion_end_tick = time.ticks_add(time.ticks_ms(), 10000)  # 顯示 10 秒
            last_display_mode = None

    except Exception as e:
        print("MQTT parse error:", e)


# 建立與連接 MQTT 客戶端
try:
    broker_ip = MQTT_BROKER
    if type(MQTT_BROKER) == str and MQTT_BROKER.endswith(".local"):
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


def send_data(t, h, m, r, l, watering, water_empty=False):
    data = {
        "temp": t,
        "hum": h,  # 對應後端 data.get("hum")
        "soil": m,  # 對應後端 data.get("soil")
        "moisture_raw": r,
        "lux": l,
        "watering": watering,
        "water_empty": water_empty,
    }
    payload = json.dumps(data)
    try:
        client.publish(TOPIC_SENSOR, payload)
        print("Published:", payload)
    except Exception as e:
        print("MQTT Publish Error:", e)


# 預設感測器初始值 (改為 None，代表未取得數據)
t = h = m = r = l = None
w_empty = False

# --- 雙電源模式防呆邏輯 ---
if POWER_MODE == "battery":
    print("🔋 [Battery Mode] 讀取一次數據後進入深度睡眠...")
    try:
        dht_sensor.measure()
        t = round(dht_sensor.temperature(), 1)
        h = round(dht_sensor.humidity(), 1)
    except:
        t = h = None
    try:
        m, r = sm.read(
            soil_sensor, conf.get("calibrationAir"), conf.get("calibrationWater")
        )
    except Exception:
        m = r = None
    if light_sensor:
        try:
            l = int(light_sensor.lux)
        except Exception:
            l = None
    else:
        l = None

    w_empty = (water_sensor.value() == 0) if water_sensor else False

    # 傳一次就跑
    send_data(t, h, m, r, l, False, w_empty)

    # 關閉螢幕與連線
    if oled:
        try:
            oled.clear()
        except Exception:
            pass
    client.disconnect()
    print("進入 Deepsleep，預計 1 小時後甦醒...")
    deepsleep(3600000)  # 睡 3600 秒 (1小時)

print("🔌 [USB Mode] 進入電子雞常時待機模式")
while True:
    try:
        current_tick = time.ticks_ms()

        # --- 1. 灑水邏輯 ---
        if is_watering:
            if time.ticks_diff(water_end_tick, current_tick) <= 0:
                if water_relay:
                    water_relay.off()
                is_watering = False
                w_empty = (water_sensor.value() == 0) if water_sensor else False
                # 狀態改變後立即回報
                send_data(t, h, m, r, l, is_watering, w_empty)

        # --- 1.5 即時偵測水位變化 ---
        if water_sensor:
            current_w_empty = water_sensor.value() == 0
            if current_w_empty != w_empty:
                w_empty = current_w_empty
                print("即時觸發：水位狀態改變 ->", "缺水" if w_empty else "有水")
                send_data(t, h, m, r, l, is_watering, w_empty)

        # --- 2. 非阻塞感測器讀取 ---
        if time.ticks_diff(current_tick, last_sensor_read) > sensor_interval:
            try:
                dht_sensor.measure()
                t = round(dht_sensor.temperature(), 1)
                h = round(dht_sensor.humidity(), 1)
            except:
                t = h = None  # 明確標示讀出失敗，讓後端能觸發安全警報

            try:
                m, r = sm.read(
                    soil_sensor,
                    conf.get("calibrationAir"),
                    conf.get("calibrationWater"),
                )
            except Exception:
                m = r = None

            if light_sensor:
                try:
                    l = int(light_sensor.lux)
                except Exception:
                    l = None
            else:
                l = None

            w_empty = (water_sensor.value() == 0) if water_sensor else False
            # 定期發送數據
            send_data(t, h, m, r, l, is_watering, w_empty)

            # 根據是否在情緒展示期間決定顯示內容
            if time.ticks_diff(emotion_end_tick, current_tick) > 0:
                pass  # 表情顯示中，暫不顯示感測器數值
            elif not is_watering:
                if oled:
                    try:
                        oled.clear()
                        oled.show_text(f"Temp: {t:>5} C", 0, 0)
                        oled.show_text(f"Hum:  {h:>5} %", 0, 16)
                        oled.show_text(f"Soil: {m:>5} %", 0, 32)
                        oled.show_text(f"Lux:  {l:>5} lx", 0, 48)
                    except Exception:
                        pass
                last_display_mode = "info"

            last_sensor_read = current_tick

        # --- 3. 動態表情與狀態顯示 ---
        if time.ticks_diff(emotion_end_tick, current_tick) > 0:
            if last_display_mode != current_emotion:
                if oled:
                    try:
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
                    except Exception:
                        pass
                last_display_mode = current_emotion
        elif (
            not is_watering
            and last_display_mode != "off"
            and time.ticks_diff(current_tick, last_sensor_read) > 10000
        ):
            # 每 10 秒後無情緒顯示則關閉螢幕省電
            if oled:
                try:
                    oled.clear()
                except Exception:
                    pass
            last_display_mode = "off"

        # --- 4. 指令解析 (MQTT 回呼) ---
        try:
            client.check_msg()
        except Exception as e:
            print("MQTT Check Msg Error:", e)

        time.sleep_ms(50)  # 提高反應速度

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        time.sleep(2)
