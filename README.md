# Smart Planter (智慧盆栽) 🌱

結合 **Raspberry Pi 5** 與 **ESP32** 的 AI 智慧盆栽系統。透過語音對話、自動澆水與環境監測，打造有「人格」的植物夥伴。

> **架構特色**：本專案採用 **去中心化網頁架構 (Decentralized Web Architecture)**。每台裝置皆為獨立運作的 Web Server，支援透過 **mDNS** 在區網內自動發現鄰近裝置，無需依賴雲端伺服器。

## 🛠 技術架構 (Tech Stack)

### 硬體 (Hardware)
- **Gateway**: Raspberry Pi 5 (Web Server, AI 運算, 影像處理)
- **MCU**: ESP32 (感測器讀取, 馬達控制, 透過 USB Serial 連接)
- **Sensors**: 土壤濕度, DHT22 (溫濕度), 光敏電阻, Pi Camera

### 軟體 (Software)
- **Backend**: Python 3, FastAPI
- **Database**: SQLite (單機輕量化儲存)
- **Template Engine**: Jinja2 (SSR 伺服器端渲染)
- **Frontend Interaction**: [htmx](https://htmx.org/) (AJAX/動態更新) + [Alpine.js](https://alpinejs.dev/) (UI 互動)
- **CSS Framework**: Tailwind CSS
- **Service Discovery**: mDNS / Zeroconf (自動發現鄰近裝置)
- **AI**: Ollama (LLM), Whisper (STT), gTTS/pyttsx3 (TTS)

---

## 🚀 快速開始 (Quick Start)

### 1. 環境設定
請確保你的電腦或 Pi 已安裝 Python 3.10+。

```bash
# Clone 專案
cd Desktop
git clone https://github.com/zenocode123/smart_planter.git
cd smart_planter

# 建立虛擬環境 (建議)
python -m venv venv

# 啟動虛擬環境
# Mac/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 安裝依賴
pip install -r requirements.txt
```

### 2. 啟動伺服器
```bash
# 開發模式 (存檔會自動重啟)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
瀏覽器打開：`http://localhost:8000`

---

## 🤝 協作開發流程 (Git Workflow)

為避免衝突，請嚴格遵守以下流程：

### 1. 準備工作
```bash
git checkout -b <你的名字/功能名稱>  # 例如: git checkout -b zeno/sensor-api
```

### 2. 開發中同步
提交程式碼前，請先同步主分支進度：
```bash
git add .
git commit -m "feat: 新增土壤濕度讀取功能"
git pull --rebase origin main  # 抓取最新進度並重新整理
```

### 3. 整理與合併 (Pull Request)
當功能完成且測試通過後：
```bash
git rebase -i main             # (選用) 整理 commit
git push origin <你的分支名稱>  # 推送至 GitHub 開 PR
```

---

## 📂 目錄結構
```
.
├── app/
│   ├── main.py          # FastAPI 入口
│   ├── routers/         # API 路由
│   ├── templates/       # Jinja2 HTML 樣板
│   ├── static/          # CSS, JS, Images
│   └── database.py      # SQLite 連線設定
├── hardware/            # ESP32 相關程式碼 (MicroPython/C++)
├── doc/                 # 專案文件
├── requirements.txt     # Python 依賴清單
└── README.md            # 專案說明
```