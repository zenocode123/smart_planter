from machine import Pin
import time

class WaterRelay:
    def __init__(self, pin_num, inverted=True):
        """
        初始化繼電器
        :param pin_num: ESP32 的 GPIO 引腳編號
        :param inverted: 是否為低電平觸發 (Low Level Trigger)。
                         如果是，設為 True；一般高電平觸發設為 False。
        """
        self.pin = Pin(pin_num, Pin.OUT)
        self.inverted = inverted
        self.off() # 確保啟動時水泵是關閉的

    def on(self):
        """開啟繼電器"""
        if self.inverted:
            self.pin.value(0)
        else:
            self.pin.value(1)
        print("繼電器：已開啟 (開始澆水)")

    def off(self):
        """關閉繼電器"""
        if self.inverted:
            self.pin.value(1)
        else:
            self.pin.value(0)
        print("繼電器：已關閉 (停止澆水)")

    def water_seconds(self, seconds):
        """澆水指定秒數後自動關閉"""
        self.on()
        time.sleep(seconds)
        self.off()

# --- 主程式使用範例 ---

# 假設你的繼電器 IN 接在 GPIO 18
# 如果你的繼電器是低電平觸發，請改為 WaterRelay(18, inverted=True)
# relay = Pin(27, Pin.OUT)
# 關
# relay.value(1)
# relay = WaterRelay(27)
# relay.water_seconds(3)