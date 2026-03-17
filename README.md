# 🌱 Smart Planter (智慧盆栽)

這是一個專為現代邊緣運算與 AI 打造的「智慧盆栽系統」。它以 **Raspberry Pi 5** 作為中央運算大腦，結合 **ESP32** 負責前端感測與澆水控制。系統不僅具備即時環境監測與自動化排程，更無縫深度整合了 NVIDIA NIM (Llama 3.1)，賦予植物專屬的「AI 人格」，能透過生成式對話與您建立深度的情感連結。

## 🌟 Key Features (核心特色)

- **🧠 邊緣 AI 植物人格**：基於 LLM 驅動，根據植物品種自動生成傲嬌、溫柔、學術等獨特對話風格。所有對話均透過 `@with_retry_sync` 高穩定度模組與結構化輸出解析。
- **📱 Glassmorphism 頂級前端介面**：融合行動裝置優先 (`@mobile-design`) 的理念，導入現代「毛玻璃」透明美學、互動微動畫，展現奢華的視覺體驗。
- **⏱️ 分散式 IoT 感測架構**：ESP32 透過輕量化 MQTT 傳遞溫濕度、土壤水分、光照強度，支援「USB 展示模式」與「電池省電深度休眠模式」。
- **🛡️ 企業級保安與效能**：SQLite 底層套用 `WAL (Write-Ahead Logging)` 高併發引擎，支援多植物查表時間索引；敏感金鑰 (Gmail App Password) 皆由 `Fernet` 對稱加密保障隱私。

---

## 🛠 Tech Stack (技術棧)

- **Language**: Python 3.11+
- **Framework**: FastAPI (非同步架構)
- **Database**: SQLite (開啟 WAL 模式) + Tortoise ORM
- **Frontend**: HTMX, Alpine.js, Jinja2, Pico CSS (客製化 Glassmorphism)
- **AI & ML**: NVIDIA NIM (Llama 3.1)
- **Hardware Comms**: MQTT 通訊協定 (Mosquitto)
- **Background Jobs**: APScheduler

---

## ⚙️ Prerequisites (必要條件)

在開始本機部署前，請確保：
- **硬體**：Raspberry Pi 5 或任何 Ubuntu/Debian 系統, ESP32-WROOM-32 (可選)。
- **套件管理**：我們全面導入 [uv](https://github.com/astral-sh/uv) 取代 pip，獲得百倍安裝速度。
- **後端服務**：本機 MQTT Broker (如 Mosquitto)。

```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients libgl1
```

---

## 🚀 Getting Started (快速啟動)

### 1. Clone the Repository
```bash
git clone https://github.com/zenocode123/smart_planter.git
cd smart_planter
```

### 2. Install Dependencies (使用 uv)
```bash
# 下載安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 自動建立虛擬環境與安裝套件
uv sync
```

### 3. Environment Setup
```bash
cp .env.example .env
```

| 變數 | 說明 | 範例 |
| :--- | :--- | :--- |
| `ENCRYPTION_KEY` | 資料庫敏感資訊加密金鑰 | 使用 `Fernet.generate_key()` 產生 |
| `JWT_SECRET_KEY` | 網頁通行證簽章金鑰 | `openssl rand -hex 32` 產生 |
| `NVIDIA_NIM_API_KEY` | 串接 AI 模型所需的合法 token | `nvapi-xxx...` |

### 4. Database Setup
本系統使用 Tortoise ORM，當 FastAPI 啟動時會自動建立 Schema 與啟用 WAL 效能優化，無須額外的遷移指令 (Migrations)。如果需要清除資料庫重新測試：
```bash
rm app/database.db
```

### 5. Start Development Server
```bash
uv run fastapi dev app/main.py
```
> 打開瀏覽器造訪 [http://localhost:8000](http://localhost:8000) 即可看到最新的絕美操作儀表板！

---

## 🏛 Architecture (系統架構)

### Directory Structure (目錄結構)
```text
├── app/
│   ├── ai/                # AI 提示詞管理、人格生成、容錯解析邏輯
│   ├── logic/             # 安全加密 (security.py)、MQTT 背景監聽
│   ├── routers/           # FastAPI 核心 API (auth.py, plants.py, chat.py)
│   ├── schemas/           # Pydantic 資料驗證模型
│   ├── static/            # CSS (style.css 視覺引擎) 與上傳的靜態資源
│   ├── templates/         # Jinja2 搭配 HTMX 的前端元件
│   ├── database.py        # 資料庫連線配置
│   ├── main.py            # 應用程式入口與 SQLite WAL 初始化
│   ├── models.py          # Tortoise ORM 資料表定義
│   └── scheduler.py       # 每日自動排程與信件發送機制
├── esp32/                 # ESP32 MicroPython 感測韌體與設定檔
└── .agent/skills/         # AI 代理人的實戰技能紀錄
```

### Data Flow (資料流向)
1. **硬體端**：ESP32 定期擷取感測器數值，並根據 `network_config.json` 的指引透過 MQTT 發送給 Raspberry Pi。
2. **通訊層**：`app/logic/mqtt_service.py` 於背景常駐，將 MQTT 收到的訊號直接寫入 SQLite 的 `PlantLog`。
3. **使用者層**：打開瀏覽器時， HTMX 會每隔幾秒對 `/plants/sensors` 發送局部更新請求，完全無痕地刷新 UI，體驗媲美 React。

### Database Schema (資料表設計)
- **`users`**: 儲存經過 BCrypt 雜湊的密碼，以及使用 Fernet 雙向加密的綁定 Gmail 應用程式密碼。
- **`plants`**: 紀錄植物血統、種類，以及專屬的 MQTT 對接頻道 (`mqtt_topic_id`)。
- **`chat_messages`**: 植物與使用者的歷史對話，具備時間戳記 `created_at` 索引優化。
- **`plant_logs`**: 儲存高頻的物聯網監測資料 (溫度、濕度、光照、土壤水分)。

---

## 🧪 Available Scripts (可用腳本)

| 指令 | 說明 |
| :--- | :--- |
| `uv run fastapi dev app/main.py` | 啟動具有存檔自動重載 (Hot-reload) 功能的開發伺服器 |
| `uv run python -c "..."`         | 執行快速測試檢索資料庫或是生成 Token 腳本 |
| `mosquitto_pub -h localhost ...` | 本機壓力測試：手動發送假的 MQTT 設備感測訊號至 broker |
| `rm app/database.db`             | 刪除 SQLite 檔案重置本地系統 |

---

## 🆘 Troubleshooting (常見問題排解)

### 問題 1：ESP32 或網頁介面顯示「Disconnected」
**診斷建議**：
1. 確保樹莓派的 Mosquitto 服務已啟動：`sudo systemctl status mosquitto`。
2. 若您剛剛清除了資料庫並重新建立植物，系統會自動分配 `p001` ID。請確保 ESP32 內部韌體確實朝著 `planter/p001/sensor` 的路徑通訊。
3. 檢查 ESP32 的供電模式是否為「Deep Sleep (深度休眠)」，該模式可能每小時才會喚醒並發送一次資料。

### 問題 2：聊天 AI 不斷回應系統錯誤
**診斷建議**：
請至 `.env` 檢查 `NVIDIA_NIM_API_KEY` 是否過期。本系統內建 Retry 容錯機制，若連續 3 次接上 NVIDIA NIM 都被拒絕，才會顯示 AI 生病了的防呆訊息。

### 問題 3：畫面按下儲存之後不會動（沒有跳轉）
**診斷建議**：
此 Bug 已在框架層由 HTMX `HX-Redirect` 與 `hx-trigger` 解決，請確保您的瀏覽器沒有開啟攔阻本機 Ajax 請求的安全套件，並可善用 `CTRL + F5` 強制更新最新的 `./static/css/style.css`。