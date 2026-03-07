from machine import Pin, ADC, I2C
import time
import sys
import json
import uselect
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
poll = uselect.poll()
poll.register(sys.stdin, uselect.POLLIN)

# 建立計時變數
last_sensor_read = 0
sensor_interval = 5000  # 每 5 秒讀一次感測器
last_display_mode = None 

print("ESP32 Ready. Sending data in JSON format...")

def send_data(t, h, m, r, l, watering):
    data = {
        "temp": t,
        "hum": h,
        "moisture": m,
        "moisture_raw": r,
        "lux": l,
        "watering": watering
    }
    print(json.dumps(data))

# 預設感測器初始值
t = h = m = r = l = 0

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
            
        # --- 4. 指令解析 (Poll) ---
        if poll.poll(0): # 不等待立即回傳
            line = sys.stdin.readline().strip()
            if line:
                try:
                    cmd = json.loads(line)
                    if cmd.get("action") == "water":
                        is_watering = True
                        sec = cmd.get("seconds", 3)
                        water_relay.on()
                        water_end_tick = time.ticks_add(time.ticks_ms(), sec * 1000)
                        # 指令確認後立即回報
                        send_data(t, h, m, r, l, is_watering)
                except:
                    pass
                
        time.sleep_ms(50) # 提高反應速度
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        time.sleep(2)
