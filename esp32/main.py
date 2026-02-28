from machine import Pin, ADC, I2C
import time 
import sys  
from dht import DHT22
import sm
from bh1750 import BH1750
from oled import OledDisplay
import json

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)
conf = sm.config()
dht_sensor = DHT22(Pin(25))
soil_sensor = ADC(Pin(26))
light_sensor = BH1750(i2c)
oled = OledDisplay(i2c=i2c)

print("ESP32 Ready. Sending data in JSON format...")

while True:
    try:
        dht_sensor.measure()
        temp = dht_sensor.temperature()
        hum = dht_sensor.humidity()
        moisture, raw = sm.read(soil_sensor, conf.get('calibrationAir'), conf.get('calibrationWater'))
        lux = light_sensor.lux
        
        # format
        t = round(temp, 1)
        h = round(hum, 1)
        m = int(moisture)
        r = int(raw)
        l = int(lux)
        
        # display
        oled.clear()
        oled.show_text(f"Temp: {t:>5} C", 0, 0)
        oled.show_text(f"Hum:  {h:>5} %", 0, 16)
        oled.show_text(f"Soil: {m:>5} %", 0, 32)
        oled.show_text(f"Lux:  {l:>5} lx", 0, 48)
        
        data = {
            "temp": t,
            "hum": h,
            "moisture": m,
            "moisture_raw": r,
            "lux": l
        }
        
        print(json.dumps(data))
        time.sleep(2)
    except Exception as e:
        error_msg = {"error": str(e)}
        print(json.dumps(error_msg))
        sys.print_exception(e)
        time.sleep(2)