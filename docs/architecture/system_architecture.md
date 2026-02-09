# 智慧盆栽 (Smart Planter) 系統架構

## 1. 架構圖 (System Architecture Diagram)

以下圖表展示了系統的三層架構：**展示層 (Client)**、**核心運算層 (Raspberry Pi)** 與 **感知控制層 (ESP32)**。

```mermaid
graph TD
    %% 加上這行，把所有 subgraph 的填色改為白色
    style Client_Layer fill:#fff,stroke:#ccc
    style RPI_Layer fill:#fff,stroke:#ccc
    style ESP_Layer fill:#fff,stroke:#ccc
    style Plant_Environment fill:#fff,stroke:#ccc
    
    %% 定義樣式 (極簡風)
    classDef user fill:#fff,stroke:#333,stroke-width:2px;
    classDef rpi fill:#fff,stroke:#333,stroke-width:2px;
    classDef esp fill:#fff,stroke:#333,stroke-width:2px;
    classDef hardware fill:#f9f9f9,stroke:#666,stroke-width:1px,stroke-dasharray: 5 5;

    %% 層級 1: 使用者與前端
    subgraph Client_Layer ["展示與互動層 (Client Layer)"]
        User["👤 使用者"] -->|瀏覽器訪問 / 操作| WebUI["🖥️ 網頁介面 (Web UI)"]
        WebUI -->|"HTTP Request (htmx)"| FASTAPI
        WebUI -.->|"WebSocket / Polling"| FASTAPI
    end

    %% 層級 2: 樹莓派 (大腦)
    subgraph RPI_Layer ["核心運算層 (Raspberry Pi 5)"]
        direction TB
        
        %% 軟體模組
        subgraph RPI_Software ["軟體服務"]
            FASTAPI["FastAPI Server<br/>(Jinja2 + htmx backend)"]
            DB[("SQLite 資料庫")]
            AI_CORE["🧠 AI 核心<br/>(Ollama / Whisper / TTS)"]
            SERIAL_MGR["🔌 Serial Manager<br/>(Python Script)"]
        end
        
        %% RPi 硬體介面
        subgraph RPI_Hardware ["多媒體硬體"]
            CAM["📷 Pi Camera<br/>(影像辨識)"]
            MIC["🎤 USB 麥克風<br/>(語音輸入)"]
            SPK["🔊 喇叭<br/>(語音回應)"]
        end

        %% 內部連線
        FASTAPI <--> DB
        FASTAPI <--> AI_CORE
        FASTAPI <--> SERIAL_MGR
        AI_CORE <--> CAM
        AI_CORE <--> MIC
        AI_CORE --> SPK
    end

    %% 通訊橋樑
    SERIAL_MGR <==>|"USB UART Serial (指令/數據)"| ESP_UART

    %% 層級 3: ESP32 (手腳)
    subgraph ESP_Layer ["感知控制層 (ESP32)"]
        direction TB
        ESP_UART["UART Handler"]
        ESP_LOGIC["控制邏輯 (Firmware)"]
        ADC["ADC (類比讀取)"]
        GPIO["GPIO (數位控制)"]

        ESP_UART <--> ESP_LOGIC
        ESP_LOGIC --> ADC
        ESP_LOGIC --> GPIO
    end

    %% 層級 4: 物理環境
    subgraph Plant_Environment ["物理盆栽環境"]
        SOIL_S["💧 土壤濕度感測器"]
        LIGHT_S["☀️ 光敏電阻"]
        PUMP["🚿 水泵馬達"]
        LAMP["💡 植物生長燈 (選配)"]
    end

    %% 物理連接
    ADC <-->|"類比訊號"| SOIL_S
    ADC <-->|"類比訊號"| LIGHT_S
    GPIO -->|"PWM 控制"| PUMP
    GPIO -->|"數位開關"| LAMP

    %% 套用樣式
    class User,WebUI user;
    class FASTAPI,DB,AI_CORE,SERIAL_MGR rpi;
    class ESP_UART,ESP_LOGIC,ADC,GPIO esp;
    class CAM,MIC,SPK,SOIL_S,LIGHT_S,PUMP,LAMP hardware;
```

---

## 2. 模組職責說明

### A. 核心運算層 (Raspberry Pi 5)
這是系統的「大腦」與「感官中心」，負責高階邏輯運算。

*   **FastAPI Server**: 處理網頁請求，使用 Jinja2 渲染 HTML 片段回傳給前端 (htmx)。
*   **AI Core**: 
    *   **視覺**: 透過 **Pi Camera** 觀察植物外觀。
    *   **聽覺**: 透過 **麥克風** 接收使用者語音，使用 Whisper 轉文字。
    *   **思考**: 使用 **Ollama** 進行自然語言對話生成。
    *   **說話**: 透過 **喇叭** 播放 TTS 生成的語音。
*   **Serial Manager**: 負責與 ESP32 進行雙向通訊，解析感測數據並存入 SQLite。

### B. 感知控制層 (ESP32)
這是系統的「神經末梢」與「四肢」，負責接觸物理世界。

*   **ADC (Analog-to-Digital Converter)**: 讀取土壤濕度與光照強度的電壓變化，轉換為 0-4095 的數值傳給 Pi。
*   **GPIO / PWM**: 接收到 Pi 的指令後，開啟水泵進行澆水，或控制生長燈開關。
*   **UART Serial**: 透過 USB 線作為忠實的傳令兵，不進行複雜決策，只回報數據與執行命令。

### C. 物理配置 (Physical Layout)
*   **樹莓派與 ESP32** 應放置於盆栽旁的**防水控制盒**中。
*   **Pi Camera** 透過控制盒上的開孔或支架，對準植物主體。
*   **感測器與水管** 從控制盒延伸至土壤中。
