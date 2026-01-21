# 專題大綱

## 壹、動機與目的

現代人因工作繁忙、空間限制等因素難以飼養寵物，轉而選擇種植植物，卻又常因缺乏時間或知識導致植物枯萎。

本專案透過嵌入式系統結合AI人格模型，打造能與使用者互動的智慧植物夥伴。系統可自動監測並照顧植物需求（澆水、環境調節），同時透過對話分享植物的狀態與「心情」，讓使用者在忙碌生活中也能輕鬆體驗照顧生命的樂趣。

## 貳、開發工具

### 一、硬體

- **中央運算單元 (Gateway)**：
  - Raspberry Pi 5 (負責 Web Server, AI 運算, 資料儲存)

- **感測與控制節點 (MCU)**：
  - ESP32 (負責讀取感測器數值、控制馬達，透過 Serial 或 WiFi 與 Pi 溝通)
  - 擴充控制板/Input Shield (整合按鈕、狀態燈號等)

- **感測器模組 (連接至 ESP32 或 Pi)**：
  - 電容式土壤濕度感測器
  - 環境溫濕度感測器（DHT22）
  - 光敏電阻/光照度感測器
  - 鏡頭模組 Pi Camera (連接至 Pi)
  - 人體紅外線感測器 HC-SR501

- **執行機構**：
  - 5V 沉水馬達（水泵）
  - 繼電器模組（控制馬達）

- **音訊模組 (連接至 Pi)**：
  - USB 麥克風
  - 3.5mm 喇叭 或 USB喇叭
  
- **其他零件**：
  - 透明水管(PVC)
  - 儲水槽
  - 杜邦線
  - 麵包板

### 二、軟體

- **作業系統**：Raspberry Pi OS（64-bit）

- **後端開發**：
  - 語言：Python 3.x
  - 框架：FastAPI
  - 樣板引擎：Jinja2 (負責伺服器端渲染)
  - 資料庫：SQLite (輕量化儲存)
  - ORM：SQLAlchemy 或 Tortoise-ORM

- **前端開發**：
  - 互動邏輯：htmx (處理 AJAX 請求與局部更新), Alpine.js (輕量級狀態管理)
  - 樣式：Tailwind CSS 或 Bootstrap
  - 結構：HTML5 / CSS3

- **AI模型**：
  - 語音辨識：Whisper (OpenAI) 或 Vosk
  - 語言模型：Ollama (本地運行) 或 Claude API
  - 語音合成：pyttsx3 或 gTTS

- **通訊協定**：
  - ESP32 <-> Pi：UART (Serial) 或 HTTP/MQTT

## 參考資料

[Turn your houseplant into a pet.](https://www.raspberrypi.com/news/turn-your-houseplant-into-a-pet/)

[Water your green friends in the simplest way you imagine.](https://medium.com/technology-hits/simplified-raspberry-pi-plant-watering-system-942099e4e2cd)

[土壤灑水控制套件(不含開發板)](https://jin-hua.com.tw/page/product/show.aspx?num=40672&kw=%e5%9c%9f%e5%a3%a4&lang=TW)
