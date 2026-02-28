import network
import time
import json

def connect_wifi():
    try:
        with open('network_config.json', 'r') as f:
            config = json.load(f)
        ssid = config['WIFI_SSID']
        password = config['WIFI_PASS']
    except Exception as e:
        print(f"讀取設定檔失敗: {e}")
        return

 
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print(f'正在連接 Wi-Fi: {ssid}...')
        wlan.connect(ssid, password)
        
      
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            print(f"等待中... 剩餘 {timeout} 秒")
            time.sleep(1)
            timeout -= 1
    
 
    if wlan.isconnected():
        print('\n--- 連線成功 ---')
        print(f'IP 位址: {wlan.ifconfig()[0]}')
        return True
    else:
        print('\n--- 連線超時或失敗 ---')
        return False


connect_wifi()