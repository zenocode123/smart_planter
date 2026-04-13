# 🌱 Smart Planter — 智慧 AI 盆栽系統

> 讓植物擁有獨特人格、能開口說話、會主動照顧自己的 AIoT 智慧盆栽平台。

基於 **Raspberry Pi 5** 作為中央大腦，結合 **ESP32** 執行感測與澆水控制，深度整合 **NVIDIA NIM (Llama 3.1-70B)** 賦予植物專屬 AI 人格。使用者可與植物即時對話、接收 Email 健康報告，系統也能根據環境數據自動決策澆水。

---

## 目錄

- [核心特色](#-核心特色)
- [系統架構圖](#-系統架構圖)
- [技術棧](#-技術棧)
- [硬體需求](#-硬體需求)
- [快速啟動](#-快速啟動)
- [環境變數參考](#-環境變數參考)
- [目錄結構](#-目錄結構)
- [資料庫設計](#-資料庫設計)
- [系統工作流程](#-系統工作流程)
- [ESP32 韌體說明](#-esp32-韌體說明)
- [可用指令](#-可用指令)
- [常見問題排解](#-常見問題排解)

---

## ✨ 核心特色

| 功能 | 說明 |
|------|------|
| **🧠 AI 植物人格** | 由 NVIDIA NIM Llama 3.1-70B 驅動，根據植物品種自動生成傲嬌、溫柔、學術等獨特對話風格 |
| **💬 即時 AI 對話** | 植物能融合感測器當前狀態（溫濕度、土壤、光照）自然回覆，口渴時會主動抱怨 |
| **⏰ 定時自動排程** | 每 2 分鐘自動拍照、執行 AI 健康分析、視需要自動澆水並發送 Email 報告 |
| **🛡️ 多層澆水防呆** | 感測器異常檢測 → AI 建議諮詢 → 水箱空狀態阻斷 → MQTT 指令發送，層層把關 |
| **📊 歷史趨勢圖** | Matplotlib 繪製 4 合 1 趨勢圖（溫度、濕度、光照、土壤），以 PNG BLOB 存入資料庫 |
| **📧 Email 健康推播** | 附帶植物照片 + 趨勢圖的 HTML Email，支援斷線警告與感測器異常警報 |
| **🎨 毛玻璃 UI** | Glassmorphism 設計語言，行動裝置優先，支援深色/淺色主題切換 |
| **🔒 企業級安全** | Fernet 對稱加密 Gmail 密碼、BCrypt 雜湊使用者密碼、JWT Token 驗證、SQLite WAL |

---

## 🏛 系統架構圖

```
┌─────────────────────────────────────────────────────┐
│                 使用者瀏覽器 (Frontend)                │
│   HTMX (AJAX)  ·  Alpine.js (狀態)  ·  Pico CSS     │
└────────────────────────┬────────────────────────────┘
                         │ HTTP / REST
┌────────────────────────▼────────────────────────────┐
│            Raspberry Pi 5 (後端伺服器)                │
│                                                     │
│  FastAPI (app/main.py)                              │
│  ├── /auth/*    使用者驗證 (JWT + BCrypt)            │
│  ├── /plants/*  感測器監控 & 澆水控制                │
│  └── /chat/*    AI 對話 (NVIDIA NIM)                │
│                                                     │
│  APScheduler ──► 每 2 分鐘                          │
│  ├── rpicam-still 拍照                              │
│  ├── NVIDIA NIM AI 健康分析                         │
│  ├── aiosmtplib Email 推播                          │
│  └── MQTT 澆水指令                                  │
│                                                     │
│  SQLite (WAL) + Tortoise ORM                        │
│  MQTT Service (paho-mqtt 背景監聽)                   │
└────────────────────────┬────────────────────────────┘
                         │ MQTT (paho)
┌────────────────────────▼────────────────────────────┐
│            Mosquitto MQTT Broker                    │
│         (Raspberry Pi 本機 port 1883)                │
└────────────────────────┬────────────────────────────┘
                         │ MQTT (Wi-Fi)
┌────────────────────────▼────────────────────────────┐
│                    ESP32                            │
│  感測器：DHT11 · BH1750 · 電容式土壤 · 水位偵測      │
│  執行器：繼電器 → 5V 水泵                           │
│  顯示：OLED (SSD1306)                               │
└─────────────────────────────────────────────────────┘
```

---

## 🛠 技術棧

| 類別 | 技術 |
|------|------|
| **語言** | Python 3.11+ / MicroPython (ESP32) |
| **後端框架** | FastAPI 0.135 + Uvicorn (非同步 ASGI) |
| **資料庫** | SQLite (WAL 模式) + Tortoise ORM 1.1.6 |
| **前端** | HTMX 1.9.10 · Alpine.js · Jinja2 · Pico CSS (客製 Glassmorphism) |
| **AI 推論** | NVIDIA NIM (Llama 3.1-70B-Instruct) via OpenAI-compatible API |
| **IoT 通訊** | MQTT (paho-mqtt 2.1.0 + Mosquitto Broker) |
| **排程** | APScheduler 3.11.2 |
| **加密** | Cryptography 46 (Fernet) · Passlib BCrypt · python-jose JWT |
| **視覺化** | Matplotlib 3.10 + Pandas 3.0 |
| **Email** | aiosmtplib 5.1 (Gmail SMTP + App Password) |
| **相機** | rpicam-still (優先) / OpenCV 4.13 (備援) |
| **套件管理** | uv (取代 pip，速度快 10-100x) |

---

## ⚙️ 硬體需求

### 必要硬體

| 元件 | 規格 | 用途 |
|------|------|------|
| **Raspberry Pi 5** | 4GB RAM 以上建議 | 中央運算、Web Server、AI 推論 |
| **ESP32-WROOM-32** | 任意開發板 | 感測器讀取、繼電器控制 |
| **DHT11 / DHT22** | GPIO 25 | 溫濕度感測 |
| **BH1750** | I2C (SCL=22, SDA=21) | 光照強度 (lux) |
| **電容式土壤感測器** | ADC GPIO 32 | 土壤濕度 (0~100%) |
| **水位浮球感測器** | GPIO 33 (上拉) | 水箱缺水偵測 |
| **繼電器模組 (5V)** | GPIO 27 | 控制水泵 |
| **5V 沉水馬達** | — | 執行澆水 |
| **OLED 顯示屏** | SSD1306 / I2C | 即時狀態顯示 |

### 選配硬體

| 元件 | 用途 |
|------|------|
| **Pi Camera Module 3** | 定時拍照、Email 附件 |
| **儲水槽 + 透明水管** | 自動澆水系統 |

---

## 🚀 快速啟動

### 1. Clone 專案

```bash
git clone https://github.com/zenocode123/smart_planter.git
cd smart_planter
```

### 2. 安裝 uv 套件管理工具

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # 或重開終端機
```

### 3. 建立虛擬環境並安裝依賴

```bash
uv sync
```

> 這一步會自動建立 `.venv/` 並安裝 `pyproject.toml` 中所有套件，約需 1-3 分鐘。

### 4. 安裝系統依賴

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients libgl1 libglib2.0-0
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### 5. 設定環境變數

```bash
cp .env.example .env
```

用任意編輯器開啟 `.env` 並填入以下關鍵欄位（詳見[環境變數參考](#-環境變數參考)）：

```bash
# 最少需要填寫這三項才能啟動
NVIDIA_NIM_API_KEY=nvapi-xxxxxxxxxxxx
ENCRYPTION_KEY=<執行 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 產生>
SECRET_KEY=<執行 openssl rand -hex 32 產生>
```

### 6. 啟動開發伺服器

```bash
uv run fastapi dev app/main.py
```

打開瀏覽器造訪 [http://localhost:8000](http://localhost:8000)

> 首次啟動時，Tortoise ORM 會自動建立 SQLite 資料表並套用 WAL 最佳化，無需手動執行 migrations。

### 7. 燒錄 ESP32 韌體（選配）

```bash
# 修改 esp32/network_config.json 填入 Wi-Fi 與 MQTT 設定
# 使用 Thonny 或 mpremote 將 esp32/ 目錄下所有檔案上傳至 ESP32
```

---

## 🔑 環境變數參考

`.env.example` 內含所有變數範本，以下為完整說明：

### 必填變數

| 變數 | 說明 | 如何取得 |
|------|------|--------|
| `NVIDIA_NIM_API_KEY` | NVIDIA NIM API 金鑰 | [build.nvidia.com](https://build.nvidia.com) 免費申請 |
| `NVIDIA_MODEL_NAME` | 使用的 LLM 模型 | 預設 `meta/llama-3.1-70b-instruct` |
| `NVIDIA_NIM_BASE_URL` | NIM API 端點 | `https://integrate.api.nvidia.com/v1` |
| `ENCRYPTION_KEY` | Fernet 加密金鑰（保護 Gmail 密碼） | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SECRET_KEY` | JWT Token 簽章金鑰 | `openssl rand -hex 32` |

### 選填變數

| 變數 | 說明 | 預設值 |
|------|------|------|
| `ALGORITHM` | JWT 簽章演算法 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_SECONDS` | Token 過期時間（秒） | `3600` |
| `MQTT_BROKER_HOST` | MQTT Broker 主機名稱 | `localhost` |
| `MQTT_BROKER_PORT` | MQTT Broker 連接埠 | `1883` |
| `SYSTEM_UPDATE_INTERVAL` | 前端感測器輪詢間隔（秒） | `5` |
| `DEFAULT_WATERING_SECONDS` | 預設每次澆水時長（秒） | `3` |

### 驗證設定是否正確

```bash
uv run python test_system.py
```

此腳本會逐一測試資料庫連線、AI API、MQTT Broker、Email 設定，並輸出體檢報告。

---

## 📁 目錄結構

```
smart_planter/
├── app/
│   ├── ai/
│   │   ├── prompts.py          # 3 個核心 Prompt 管理引擎（排程分析、聊天、人格生成）
│   │   └── personality.py      # AI 植物人格生成（調用 NVIDIA NIM）
│   ├── logic/
│   │   ├── mqtt_service.py     # MQTT 背景監聽服務單例，即時寫入 PlantLog
│   │   ├── security.py         # Fernet 對稱加密 / 解密工具
│   │   ├── camera.py           # rpicam-still + OpenCV 相機拍照，PNG 浮水印
│   │   ├── mailer.py           # 非同步 SMTP Email，附帶植物照片 + 趨勢圖
│   │   └── dataviz.py          # Matplotlib 4 合 1 趨勢圖生成（PNG BytesIO）
│   ├── routers/
│   │   ├── auth.py             # 使用者登入 / 註冊 / 登出（JWT + HttpOnly Cookie）
│   │   ├── plants.py           # 感測器讀取、澆水控制、AI 諮詢、歷史報表
│   │   └── chat.py             # AI 對話生成（HTMX streaming pattern）
│   ├── schemas/
│   │   └── plant.py            # Pydantic 資料驗證模型
│   ├── static/
│   │   ├── css/
│   │   │   ├── pico.green.min.css   # Pico CSS 綠色主題
│   │   │   └── style.css            # 客製化 Glassmorphism 樣式（918 行）
│   │   ├── js/
│   │   │   ├── htmx.min.js     # HTMX 1.9.10
│   │   │   ├── alpine.min.js   # Alpine.js
│   │   │   └── app.js          # 自訂前端邏輯（澆水輪詢、Toast、主題切換）
│   │   └── uploads/            # 使用者上傳照片 & 相機拍照快取
│   ├── templates/
│   │   ├── base.html           # 基礎 HTML 框架（Sidebar、NavBar、主題切換）
│   │   ├── index.html          # 主儀表板（感測器卡片、澆水按鈕、AI 建議）
│   │   ├── chat.html           # AI 對話頁（HTMX 雙階段生成）
│   │   ├── chat_fragment.html  # 聊天訊息片段（使用者 + 思考中 + AI 回覆）
│   │   ├── sensor_fragment.html # 感測器數據 HTMX 局部更新片段
│   │   ├── plant_settings.html # 植物設定（暱稱、品種、日期、AI 人格、照片）
│   │   ├── reports.html        # 歷史報告（趨勢圖 BLOB、舊日誌列表）
│   │   ├── ai_watering_confirm.html # AI 澆水建議確認彈窗
│   │   ├── water_warning_modal.html # 感測器異常澆水警告彈窗
│   │   └── login.html / register.html
│   ├── database.py             # Tortoise ORM 連線配置 + WAL 初始化
│   ├── main.py                 # FastAPI 應用入口、路由掛載、lifespan 事件
│   ├── models.py               # ORM 資料表定義（5 個模型）
│   ├── auth.py                 # JWT 驗證邏輯、密碼雜湊、依賴注入
│   └── scheduler.py            # APScheduler 定時健康排程（每 2 分鐘）
├── esp32/
│   ├── main.py                 # ESP32 MicroPython 主程式（感測 + MQTT + OLED）
│   ├── network_config.json     # Wi-Fi SSID、MQTT Broker、Client ID 設定
│   └── sm_config.json          # 土壤感測器 ADC 校準值（空氣 / 水中）
├── docs/
│   ├── project/                # 專題大綱與動機說明
│   └── use_case/               # UC01-UC12 使用案例文件
├── .env.example                # 環境變數範本（20 個變數，含說明）
├── pyproject.toml              # uv 套件依賴清單
├── test_system.py              # 系統體檢腳本
└── README.md
```

---

## 🗄 資料庫設計

系統使用 SQLite（WAL 模式）搭配 Tortoise ORM，啟動時自動建表。

```
users
├── id              INTEGER  PK
├── username        VARCHAR  NOT NULL UNIQUE
├── email           VARCHAR  NOT NULL UNIQUE
├── hashed_password VARCHAR  NOT NULL          -- BCrypt 雜湊
└── gmail_app_password VARCHAR               -- Fernet 加密，可為 NULL

plants
├── id              INTEGER  PK
├── user_id         FK → users
├── nickname        VARCHAR                    -- 植物暱稱（如「多多」）
├── species         VARCHAR                    -- 品種（如「虎尾蘭」）
├── mqtt_topic_id   VARCHAR  DEFAULT 'planter_01'
├── ai_personality  TEXT                       -- 由 AI 自動生成的人格描述
├── photo_path      VARCHAR                    -- 使用者上傳照片路徑
└── created_at      DATETIME INDEX

chat_messages
├── id              INTEGER  PK
├── plant_id        FK → plants
├── role            VARCHAR  -- 'user' | 'assistant'
├── content         TEXT
└── created_at      DATETIME INDEX

plant_logs
├── id              INTEGER  PK
├── plant_id        FK → plants
├── temperature     FLOAT
├── humidity        FLOAT
├── soil_moisture   FLOAT
├── lux             FLOAT
├── photo_path      VARCHAR
├── photo_blob      BLOB                       -- PNG 照片二進制
├── chart_blob      BLOB                       -- Matplotlib 趨勢圖 PNG
├── ai_analysis     TEXT                       -- AI 健康分析 JSON
└── created_at      DATETIME INDEX

watering_logs
├── id              INTEGER  PK
├── plant_id        FK → plants
├── source          VARCHAR  -- 'manual' | 'system'
├── duration        FLOAT    -- 澆水秒數
└── created_at      DATETIME INDEX
```

**效能最佳化**

```sql
-- 啟動時自動執行
PRAGMA journal_mode=WAL;        -- 高併發讀寫
PRAGMA synchronous=NORMAL;      -- 解決 "database is locked"
```

---

## 🔄 系統工作流程

### 感測器資料流

```
ESP32（每 60 秒）
  └─► MQTT Publish: planter/planter_01/sensor
      {"temp": 25.3, "hum": 60, "soil": 72, "lux": 1200,
       "watering": false, "water_empty": false}
        │
        ▼
Raspberry Pi - MQTT Service（背景監聽）
  └─► 寫入 PlantLog + 更新 latest_update_time 快取
        │
        ▼
前端 HTMX（每 5 秒輪詢 /plants/sensors）
  └─► 局部更新感測器卡片，無頁面重整
```

### 定時排程（每 2 分鐘）

```
APScheduler: daily_plant_routine()
  ├── 1. 檢查 MQTT 連線（120s 無更新 = 離線 → 發送斷線 Email）
  ├── 2. 感測器異常過濾
  │       溫度 < -20°C 或 > 80°C
  │       濕度 < 0% 或 > 100%
  │       土壤 < 0% 或 > 100%
  │       光照 < 0 或 > 200,000 lux
  ├── 3. rpicam-still 拍照（失敗時退回 OpenCV）
  ├── 4. NVIDIA NIM AI 分析（JSON 輸出 message + water_seconds）
  ├── 5. Matplotlib 趨勢圖生成
  ├── 6. 建立 PlantLog（存入 photo_blob + chart_blob）
  ├── 7. Gmail SMTP 發送 HTML Email（附帶照片 + 趨勢圖）
  └── 8. 若 water_seconds > 0 → MQTT Publish 澆水指令
          {"action": "water", "duration": 2.5}
```

### 手動澆水流程

```
使用者點擊「澆水」
  ├── 檢查 MQTT 連線（65s 無更新 = 網路離線）
  ├── 檢查水箱（water_empty = true → 彈窗阻斷）
  ├── 感測器異常檢測
  │   └── 有異常 → water_warning_modal.html
  │       ├── 強制澆水（1.0 秒，bypass AI）
  │       └── 取消
  └── 無異常 → AI 諮詢 NVIDIA NIM
      └── ai_watering_confirm.html（顯示建議秒數）
          ├── 確認 → MQTT 發送指令 + 記錄 WateringLog
          └── 取消
```

### AI 對話雙階段生成

```
使用者送出訊息
  │
  ├─► POST /chat/
  │     存入 ChatMessage(role=user)
  │     回傳：使用者氣泡 + 「思考中」佔位符（hx-trigger="load"）
  │
  └─► 自動觸發 POST /chat/generate/{id}
        讀取最近 9 條對話歷史
        組合 system prompt（人格 + 品種 + 即時感測器數據）
        NVIDIA NIM API（@with_retry_sync 最多重試 3 次）
        存入 ChatMessage(role=assistant)
        回傳 AI 氣泡（HTMX outerHTML 替換佔位符）
```

---

## 📡 ESP32 韌體說明

### 硬體接線

| 感測器/元件 | 接腳 | 協定 |
|------------|------|------|
| DHT11 (溫濕度) | GPIO 25 | 單線協定 |
| BH1750 (光照) | SCL=22, SDA=21 | I2C |
| 土壤感測器 | GPIO 32 (ADC) | ADC 類比 |
| 水位感測器 | GPIO 33 (上拉) | 數位 |
| 繼電器 | GPIO 27 | 數位輸出 |
| OLED (SSD1306) | SCL=22, SDA=21 | I2C |

### 設定檔說明

**`esp32/network_config.json`**

```json
{
    "WIFI_SSID": "你的Wi-Fi名稱",
    "WIFI_PASSWORD": "你的Wi-Fi密碼",
    "MQTT_BROKER": "raspberrypi.local",
    "CLIENT_ID": "planter_01",
    "TOPIC_SENSOR": "planter/planter_01/sensor",
    "TOPIC_CMD": "planter/planter_01/cmd",
    "POWER_MODE": "usb"
}
```

> `POWER_MODE` 可設為 `"usb"`（常駐模式）或 `"battery"`（深度睡眠省電模式）。

**`esp32/sm_config.json`** — 土壤感測器校準

```json
{
    "calibrationAir": 4095,
    "calibrationWater": 1500,
    "step": 60000
}
```

> 校準方式：將感測器置於空氣中記錄 ADC 值填入 `calibrationAir`，插入水中記錄填入 `calibrationWater`。

### MQTT 訊息格式

**感測器上報（ESP32 → Pi）**

```json
{
    "temp": 25.3,
    "hum": 60.1,
    "soil": 72.5,
    "lux": 1200,
    "watering": false,
    "water_empty": false,
    "moisture_raw": 0.724
}
```

**澆水指令（Pi → ESP32）**

```json
{"action": "water", "duration": 2.5}
```

**情緒指令（Pi → ESP32）**

```json
{"emotion": "happy"}
```

---

## 📋 可用指令

| 指令 | 說明 |
|------|------|
| `uv run fastapi dev app/main.py` | 啟動開發伺服器（支援 Hot-reload） |
| `uv run fastapi run app/main.py` | 啟動生產模式伺服器 |
| `uv run python test_system.py` | 執行全系統體檢（DB / AI / MQTT / Email） |
| `uv run python check.py` | 查看 WateringLog 澆水紀錄筆數 |
| `rm app/database.db` | 清除資料庫（重置系統） |
| `sudo systemctl status mosquitto` | 確認 MQTT Broker 運作狀態 |
| `mosquitto_pub -h localhost -t "planter/planter_01/sensor" -m '{"temp":25,"hum":60,"soil":70,"lux":1000,"watering":false,"water_empty":false}'` | 手動發送模擬感測器數據（除錯用） |

---

## 🆘 常見問題排解

### 問題 1：植物顯示「裝置離線 / Disconnected」

**原因**：超過 65 秒未收到 ESP32 的 MQTT 訊息。

**排查步驟**：

```bash
# 1. 確認 Mosquitto 正在運行
sudo systemctl status mosquitto

# 2. 測試 Broker 是否可接收訊息
mosquitto_sub -h localhost -t "planter/planter_01/sensor"

# 3. 若 ESP32 為電池模式，每小時才會喚醒，可改為 USB 模式
# 修改 esp32/network_config.json 中 "POWER_MODE": "usb"
```

### 問題 2：AI 聊天顯示「植物在發呆，沒有回應」

**原因**：NVIDIA NIM API 金鑰無效或額度用盡（系統已內建重試 3 次）。

```bash
# 確認金鑰設定
grep NVIDIA_NIM_API_KEY .env

# 測試 API 連線
uv run python test_system.py
```

### 問題 3：排程出現 ImportError（get_ram_path）

如果 logs 出現：
```
ImportError: cannot import name 'get_ram_path' from 'app.logic.camera'
```

此為 `mailer.py` 引用了已不存在的函式，請確認 `app/logic/camera.py` 與 `app/logic/mailer.py` 版本一致。

### 問題 4：Firefox 聊天氣泡看不見

**原因**：Firefox 對 `backdrop-filter` CSS 屬性支援度與 Chrome 不同，導致舊版 assistant 氣泡幾乎透明。

已於 `app/static/css/style.css` 中修正 `--bubble-assistant` 為不透明背景色，清除瀏覽器快取（`Ctrl + F5`）後即可。

### 問題 5：相機拍照失敗

```
⚠️ rpicam-still 拍照發生錯誤 (exit status 255)
⚠️ OpenCV 無法開啟相機設備
```

**原因**：Pi Camera 未連接或相機介面未啟用。

```bash
# 啟用相機介面
sudo raspi-config
# → Interface Options → Camera → Enable

# 測試相機
rpicam-still -n --timeout 2000 -o test.jpg
```

> 無相機時，排程仍會正常執行健康分析與 Email，僅跳過拍照步驟。

### 問題 6：資料庫鎖定（database is locked）

系統已啟用 `PRAGMA journal_mode=WAL` 大幅降低此問題發生機率。若仍出現：

```bash
# 確認沒有殭屍程序佔用
fuser app/database.db

# 或重啟伺服器
```

---

## 📐 資料流向總覽

```
硬體層（ESP32）
  感測器讀取（60秒）→ MQTT Publish → planter/+/sensor

通訊層（Mosquitto MQTT Broker）

伺服器層（Raspberry Pi 5）
  MQTT Service（背景常駐）→ PlantLog 即時寫入
  FastAPI Routes
    /auth/*     → JWT + BCrypt + HttpOnly Cookie
    /plants/*   → 感測器讀取、AI 澆水諮詢、歷史報表
    /chat/*     → NVIDIA NIM 雙階段串流生成
  APScheduler（每 2 分鐘）
    拍照 → AI 分析 → Email → MQTT 澆水
  SQLite（WAL）

前端層（使用者瀏覽器）
  Jinja2 模板 → HTMX AJAX 局部更新 → Alpine.js 反應式狀態
```

---

## 📄 License

本專案為學術專題，僅供教育與展示用途。
