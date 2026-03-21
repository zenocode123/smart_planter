import network
import json
import time

def connect_wifi():
    try:
        with open('network_config.json', 'r') as f:
            config = json.load(f)
        
        ssid = config.get('WIFI_SSID')
        password = config.get('WIFI_PASS')
        
        if not ssid:
            print("WIFI_SSID 未在設定檔中找到")
            return False

        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            print(f'正在連接 Wi-Fi: {ssid}...')
            wlan.connect(ssid, password)
            
            # 等待連線
            timeout = 15
            while not wlan.isconnected() and timeout > 0:
                print(".", end="")
                time.sleep(1)
                timeout -= 1
                
        if wlan.isconnected():
            print('\n--- WiFi 連線成功 ---')
            print(f'IP 位址: {wlan.ifconfig()[0]}')
            return True
        else:
            print('\n--- WiFi 連線超時或失敗 ---')
            return False
            
    except Exception as e:
        print(f"WiFi 連線發生錯誤: {e}")
        return False

# 當被 import 或是直接執行時，啟動連線
connect_wifi()