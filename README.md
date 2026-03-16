# Smart Planter (智慧盆栽) 🌱

結合 **Raspberry Pi 5** 與 **ESP32** 的 AI 智慧盆栽系統。透過語音對話、自動澆水與環境監測，打造有「人格」的植物夥伴。

> **架構特色**：本專案採用 **去中心化網頁架構 (Decentralized Web Architecture)**。每台裝置皆為獨立運作的 Web Server，支援透過 **mDNS** 在區網內自動發現鄰近裝置，無需依賴中央雲端伺服器。

## 🛠 技術架構 (Tech Stack)

### 1. 硬體分工 (Hardware Breakdown)

| 裝置 | 角色 | 連接週邊 / 職責 |
| :--- | :--- | :--- |
| **Raspberry Pi 5** | 伺服器 | Pi Camera (影像辨識), AI 運算 (Ollama), Web Server, 資料庫 |
| **ESP32** (via USB) | 感測器讀取 | OLED 螢幕, DHT22 (溫濕度), BH1750 (光照), 土壤濕度感測器, 水泵馬達 |

### 2. 軟體棧 (Software Stack)
- **Backend**: Python 3.11, FastAPI (Async)
- **Database**: SQLite (SQLAlchemy / Tortoise-ORM)
- **Frontend**: Jinja2 (SSR) + **htmx** (Dynamic updates) + **Alpine.js** (Client state)
- **Styling**: **Pico CSS** (Minimalist framework) + `style.css`
- **AI Engine**: Ollama (LLM), Whisper (STT), gTTS (TTS)
- **Communication**: USB Serial (Raspberry Pi <-> ESP32)
- **Networking**: Port 80, mDNS (raspberrypi.local)

### 💡 前端開發備註 (Frontend Notes)
本專案採用 **htmx + Alpine.js + Pico CSS** 的極簡組合：
- **Pico CSS 注意事項**：Pico 內建了模態視窗 (Modal) 邏輯。若在 `<body>` 使用 `.modal-is-open` 類別，Pico 會建立一個隱形的層級來鎖定頁面，這曾與自定義側邊欄產生 `z-index` 衝突（導致看得到但點不到連結）。
- **解決方案**：目前側邊欄完全由 Alpine.js 獨立控制狀態，並將 `z-index` 提升至 `9999` 以確保互動權限。

---

## 🚀 快速開始 (Quick Start)

### 1. 環境設定
⭐️ Python 3.11+。

```bash
# Clone 專案
git clone https://github.com/zenocode123/smart_planter.git
cd ~/smart_planter

# 建立並啟動虛擬環境
python -m venv .venv

# 啟動虛擬環境
.venv/Scripts/activate

# 安裝依賴
pip install -r requirements.txt

uvicorn app.main:app --reload
```

#### Demo
透過 `systemd` 服務在背景運行，開機自動啟動。
```bash
# 啟動服務
sudo systemctl start smart-planter.service

# 停止服務 (若要改用開發模式測試，必須先停止這個)
sudo systemctl stop smart-planter.service

# 檢查狀態
sudo systemctl status smart-planter.service

# 設定/取消 開機自動啟動
sudo systemctl enable smart-planter.service
sudo systemctl disable smart-planter.service
```
手機存取網址：`http://raspberrypi.local` (無需輸入 Port)

### 2. Ollama AI 引擎管理
本專案使用 [Ollama](https://ollama.ai) 在本地運行 `phi3:mini` 模型，用於生成植物 AI 人格。

```bash
# 確認服務狀態
systemctl status ollama

# 查看目前載入的模型（是否在推理中）
ollama ps

# 即時監控 Ollama 日誌（按 Ctrl+C 退出）
journalctl -u ollama -f

# 測試 API 是否正常回應
curl http://localhost:11434/api/tags

# 手動與模型對話測試
ollama run phi3:mini
```

> **💡 開發建議**：開兩個終端視窗，一個跑 `uvicorn`，另一個跑 `journalctl -u ollama -f`，這樣在網頁上「儲存植物設定」時就能即時看到 AI 推理過程。

---

### 3. AI 輔助開發設定 (Google Antigravity)
本專案支援 Antigravity 的 AI Agent 工作流。若要啟用 AI 擴充技能庫，請在專案根目錄執行：

   ```bash
# 確保你已將開源技能庫 clone 到你的電腦中
# git clone [https://github.com/guanyang/antigravity-skills.git](https://github.com/guanyang/antigravity-skills.git) ~/Desktop/antigravity-skills
# https://github.com/sickn33/antigravity-awesome-skills/blob/main/docs/users/bundles.md

# 建立技能資料夾並透過軟連結引入
   mkdir -p .agent/skills
   ln -s ~/Desktop/antigravity-skills/skills/* .agent/skills/
   ```

---

## 📂 目錄結構

```text
.
├── .agent/              # AI Agent 技能配置
├── app/
├── esp32/               # ESP32 MicroPython 程式碼
├── GEMINI.md            # AI 開發規範 (必讀)
└── README.md            # 專案說明書
```