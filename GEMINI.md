# AI 開發規範與上下文 (GEMINI.md)

這份文件定義了「智慧盆栽 (Smart Planter)」專案的開發標準、技術架構與約束條件。在生成程式碼或提供架構建議時，請嚴格遵守以下規範。

## 1. 專案概述

一個結合 **Raspberry Pi 5** 與 **ESP32** 的智慧系統。
- **架構模式**: **去中心化 (Decentralized)**。每台樹莓派都是獨立運作的 Web Server。
- **多裝置管理**: 透過前端介面的「鄰近裝置列表 (Peer Devices)」進行 IP 跳轉切換，不依賴中央雲端伺服器。
- **核心功能**: 樹莓派負責 AI 對話與高層邏輯；ESP32 負責感測器讀取與硬體控制。

## 2. 技術棧 (嚴格遵守)

- **程式語言**: Python 3.11
- **後端框架**: **FastAPI** (優先使用異步 `async`)。
- **樣板引擎**: **Jinja2** (伺服器端渲染 SSR)。
- **前端互動**:
    - 使用 **htmx** 處理所有伺服器互動（AJAX、局部重新載入）。**禁止**使用 React、Vue 或 Angular。
- **資料庫**: **SQLite** (簡單、零配置、單機儲存)。使用 `SQLAlchemy` 或 `Tortoise-ORM`。
- **硬體通訊**: 樹莓派與 ESP32 之間透過 **USB Serial (UART)** 進行通訊。

## 3. 程式碼規範

### 後端 (Python/FastAPI)
- **型別提示 (Type Hinting)**: 所有函式參數與回傳值必須標註型別。
- **異步處理**: 路由處理與資料庫操作優先使用 `async def`。
- **目錄結構**:
    - `app/routers/`: 按功能模組拆分路由 (如：`plants.py`, `dashboard.py`)。
    - `app/templates/`: HTML 檔案，使用 `base.html` 進行樣板繼承。
- **HTMX 模式**:
    - 針對 htmx 請求，回傳 **HTML 片段 (Fragments)** 而非 JSON。
    - 若需要觸發前端行為，使用 `HX-Trigger` 響應頭。

### 前端 (HTML/CSS)
- **CSS**: 優先使用原生 CSS 實作樣式。
- **HTMX 使用**:
    - 善用 `hx-get`, `hx-post`, `hx-target`, `hx-swap`。
    - 範例：`<button hx-post="/water" hx-swap="outerHTML">開始澆水</button>`

## 4. 硬體分工
- **Raspberry Pi**: 處理大腦邏輯、資料庫、Web Server、AI 運算 (Ollama/Whisper/TTS)。
- **ESP32**: 負責即時任務。讀取 ADC (土壤濕度)、控制 PWM (水泵馬達)。它作為從屬設備，聽從樹莓派的指令。

## 5. 開發新功能的典型流程
1. 定義資料庫模型 (SQLite)。
2. 建立 Pydantic Schema (資料驗證)。
3. 撰寫 FastAPI 路由 (GET 負責頁面/片段，POST 負責執行動作)。
4. 建立/更新 Jinja2 樣板，並加入 htmx 屬性。
5. (若涉及硬體) 實作 Serial 通訊協定的對應指令。