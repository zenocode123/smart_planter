from machine import Pin, ADC, I2C
import time
import sys
import json
# 引入自定義網路連線模組，確保 ESP32 啟動後能自動連上 Wi-Fi 才能進行 MQTT 通訊
import connect_wifi
# 使用 MicroPython 輕量級的 MQTT 客戶端，避免佔用過多記憶體
from umqtt.simple import MQTTClient
from dht import DHT22
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

# 外部化設定資訊，方便更換環境 (如 WiFi SSID 或 Broker IP) 而不需修改核心邏輯
with open('network_config.json', 'r') as f:
    net_config = json.load(f)
mqtt_server = net_config.get("MQTT_BROKER", "192.168.X.X")

# 建立 MQTT 客戶端實例，Client ID 固定為智慧盆栽識別碼
client = MQTTClient("smart_planter_esp32", mqtt_server)

def sub_cb(topic, msg):
    """
    MQTT 訂閱回調函式：處理來自樹莓派的指令。
    設計意圖：採用非同步指令模式，讓 ESP32 可以在不間斷感測的情況下接收遠端控制。
    """
    global is_watering, water_end_tick, t, h, m, r, l
    print("Received MQTT:", topic, msg)
    
    # 僅處理 command 主題，確保指令來源正確
    if topic == b'smart_planter/commands':
        try:
            cmd = json.loads(msg)
            # 解析動作指令，目前僅支援「澆水 (water)」
            if cmd.get("action") == "water":
                is_watering = True
                sec = cmd.get("seconds", 3)
                water_relay.on()
                # 使用系統滴答計數來計算結束時間，避免使用 sleep 導致感測器讀取中斷
                water_end_tick = time.ticks_add(time.ticks_ms(), sec * 1000)
                # 執行動作後立即回報狀態，優化前端反應速度
                send_data(t, h, m, r, l, is_watering)
        except Exception as e:
            print("Command parse error:", e)

# 註冊回調，當收到訊息時自動執行 sub_cb
client.set_callback(sub_cb)

def connect_mqtt():
    """
    建立 MQTT 連線並訂閱相關主題。
    意圖：確保雙向通訊機制就緒，ESP32 必須訂閱 commands 才能接收澆水動作。
    """
    try:
        client.connect()
        print("Connected to MQTT %s" % mqtt_server)
        client.subscribe(b"smart_planter/commands")
        return True
    except OSError as e:
        print("MQTT connect failed:", e)
        return False

# 阻塞式初始化：若未連接上 MQTT Broker 則不進入主循環，確保系統狀態一致
while not connect_mqtt():
    time.sleep(5)

# 建立計時變數
last_sensor_read = 0
sensor_interval = 5000  # 每 5 秒讀一次感測器
last_display_mode = None 

print("ESP32 Ready. Publishing data to MQTT...")

def send_data(t, h, m, r, l, watering):
    """
    彙整感測器數據並發布至 MQTT。
    意圖：將裝置狀態「主動推送」至 Broker，讓多個訂閱者 (如 RPi、手機 App) 都能取得即時資訊。
    """
    data = {
        "temp": t,
        "hum": h,
        "moisture": m,
        "moisture_raw": r,
        "lux": l,
        "watering": watering
    }
    payload = json.dumps(data)
    print("Publishing:", payload)
    try:
        # 發布至 sensors 主題，區分「感測數據」與「控制指令」
        client.publish(b"smart_planter/sensors", payload)
    except OSError as e:
        print("Publish failed:", e)

# 預設感測器初始值
t = h = m = r = l = 0

while True:
    try:
        current_tick = time.ticks_ms()
        
        # --- 1. 灑水邏輯 ---
        if is_watering:
            # 檢查是否到達設定的關閉時間 (非阻塞檢查)
            if time.ticks_diff(water_end_tick, current_tick) <= 0:
                water_relay.off()
                is_watering = False
                # 灑水結束後立即回報最新狀態
                send_data(t, h, m, r, l, is_watering)
        
        # --- 2. 非阻塞感測器讀取 ---
        if time.ticks_diff(current_tick, last_sensor_read) > sensor_interval:
            try:
                dht_sensor.measure()
                t = round(dht_sensor.temperature(), 1)
                h = round(dht_sensor.humidity(), 1)
            except:
                pass # 忽略單次讀取失敗，提高系統容錯率
            
            m, r = sm.read(soil_sensor, conf.get('calibrationAir'), conf.get('calibrationWater'))
            l = int(light_sensor.lux)
            
            # 定期發送數據，維持雲端數據新鮮度
            send_data(t, h, m, r, l, is_watering)
            
            # 更新顯示 (非灑水模式下)
            if not is_watering:
                oled.clear()
                oled.show_text(f"Temp: {t:>5} C", 0, 0)
                oled.show_text(f"Hum:  {h:>5} %", 0, 16)
                oled.show_text(f"Soil: {m:>5} %", 0, 32)
                oled.show_text(f"Lux:  {l:>5} lx", 0, 48)
                last_display_mode = "info"
            
            last_sensor_read = current_tick
            
        # --- 3. 灑水狀態顯示 ---
        if is_watering and last_display_mode != "watering":
            oled.clear()
            oled.show_center("WATERING NOW...", y=24)
            last_display_mode = "watering"
            
        # --- 4. 指令解析 (MQTT) ---
        try:
            # 非阻塞式檢查是否有新訊息，這是 MQTT 異步通訊的核心
            client.check_msg()
        except OSError as e:
            # 偵測斷線並自動嘗試恢復，確保系統長效穩定
            print("MQTT connection lost, reconnecting:", e)
            connect_mqtt()
                
        time.sleep_ms(50) # 保持毫秒級反應速度，同時給予系統閒置時間
        
    except Exception as e:
        # 捕捉全域錯誤，避免 ESP32 因為單次偶發錯誤而當機重啟
        print(json.dumps({"error": str(e)}))
        time.sleep(2)
