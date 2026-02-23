import dht
from machine import Pin
import time

sensor = dht.DHT22(Pin(3))

print("--- ESP32 DHT22 啟動 ---")

while True:
    try:
        time.sleep(2)  
        sensor.measure()
        
        t = sensor.temperature()
        h = sensor.humidity()
        
        # 檢查是否讀到合理的數值
        if t == 0 and h == 0:
            print("警告: 讀取到 0，請檢查感測器接線或供電")
        else:
            # 這是給你看的格式
            print(f"目前狀態 -> 溫度: {t}°C, 濕度: {h}%")
            # 這是保留給未來 FastAPI 機器讀取的格式
            print(f"DATA:{t},{h}")
        
    except OSError as e:
        print("Sensor Error: 讀取失敗（OSError），通常是接線斷開或沒接電阻")