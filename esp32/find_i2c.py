from machine import Pin, I2C

# 初始化 I2C (確保腳位與你實際接線一致)

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)

print("正在掃描 I2C 匯流排...")
devices = i2c.scan()

if len(devices) == 0:
    print("殘念！沒有發現任何 I2C 設備。請檢查接線與電源。")
else:
    print(f"發現 {len(devices)} 個設備：")
    for device in devices:
        # 將十進位轉成十六進位，這比較符合手冊上的標示
        print(f" - 十進位位址: {device} , 十六進位位址: {hex(device)}")
