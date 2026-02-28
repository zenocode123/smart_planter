import ssd1306

class OledDisplay:
    def __init__(self, i2c, width=128, height=64, addr=0x3C):
        self.width = width
        self.height = height
        self.i2c = i2c
        
        try:
            self.oled = ssd1306.SSD1306_I2C(width, height, self.i2c, addr=addr)
            
        except OSError:
            print("警告：找不到 OLED 螢幕，請檢查接線或位址！")
            self.oled = None
        
    def clear(self):
        if self.oled:
            self.oled.fill(0)
            self.oled.show()
            
    def show_text(self, text, x=0, y=0, clear_first=False):
        if not self.oled: return
        
        if clear_first:
            self.oled.fill(0)
        else:
            # 優化：只清除文字預計佔用的區域 (每個字約 8x8 像素)
            # 這樣不會閃爍，比全螢幕 fill(0) 更平滑
            self.oled.fill_rect(x, y, len(text) * 8, 8, 0)
        
        self.oled.text(text, x, y)
        self.oled.show()

    
    def show_center(self, text, y=32, clear_line=True):
        if not self.oled: return
        
        x = (self.width - len(text) * 8) // 2
        if clear_line:
            # 清除這一整行
            self.oled.fill_rect(0, y, self.width, 8, 0)
            
        self.oled.text(text, x, y)
        self.oled.show()