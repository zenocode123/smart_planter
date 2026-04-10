import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import matplotlib
import io
import numpy as np

# 使用非互動式 backend 避免在樹莓派背景執行時出現 GUI 錯誤
matplotlib.use('Agg')

# 定義圖片儲存目錄
PLOT_DIR = Path("app/static/plots")

async def generate_history_plot(limit: int = 50, plant_id: int = None, end_timestamp: float = None) -> io.BytesIO | None:
    """
    從資料庫中撈取最近 `limit` 筆的 PlantLog (可選指定 plant_id)，
    繪製趨勢圖並存檔。
    """
    from app.models import PlantLog
    try:
        PLOT_DIR.mkdir(parents=True, exist_ok=True)
        suffix = f"_{plant_id}" if plant_id else ""
        
        # 取得紀錄
        query = PlantLog.all().order_by("-created_at")
        if plant_id:
            query = query.filter(plant_id=plant_id)
            
        if end_timestamp is not None:
            from datetime import datetime, timezone
            end_dt = datetime.fromtimestamp(end_timestamp, tz=timezone.utc)
            query = query.filter(created_at__lte=end_dt)
            
        logs = await query.limit(limit)
        
        if not logs:
            print(f"⚠️ [DataViz] 植物 {plant_id} 尚無資料，跳過繪圖。")
            return None
            
        logs = sorted(logs, key=lambda x: x.created_at)
        
        # 轉換為 Pandas DataFrame
        data = []
        last_time = None
        for log in logs:
            if last_time and (log.created_at - last_time).total_seconds() > 300:
                # 若間隔超過 5 分鐘，插入空值斷線防呆，避免畫出錯誤的長斜線
                data.append({
                    "time": last_time + pd.Timedelta(seconds=1),
                    "temperature": None,
                    "humidity": None,
                    "moisture": None,
                    "lux": None
                })
                
            data.append({
                "time": log.created_at,
                "temperature": log.temperature,
                "humidity": log.humidity,
                "moisture": log.soil_moisture,
                "lux": log.lux
            })
            last_time = log.created_at
            
        df = pd.DataFrame(data)
        
        # 修正時區差距 (將資料庫預設的 UTC 時間轉為台灣時間 +8 小時)
        df['time'] = pd.to_datetime(df['time'])
        if df['time'].dt.tz is not None:
            df['time'] = df['time'].dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        else:
            df['time'] = df['time'] + pd.Timedelta(hours=8)
        
        if df.empty or df[['temperature', 'humidity', 'lux']].dropna(how='all').empty:
             return None

        # 開始繪圖
        fig, ax1 = plt.subplots(figsize=(8, 4))
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Temp(℃) / Hum(%)', color='tab:red')
        
        if not df['temperature'].isna().all():
            ax1.plot(df['time'], df['temperature'], color='tab:red', label='Temp', marker='o', markersize=3)
        if not df['humidity'].isna().all():
            ax1.plot(df['time'], df['humidity'], color='tab:blue', label='Hum', marker='s', markersize=3)
            
        ax1.tick_params(axis='y', labelcolor='tab:red')
        ax1.grid(True, linestyle='--', alpha=0.5)

        import matplotlib.dates as mdates

        ax2 = ax1.twinx()  
        ax2.set_ylabel('Lux', color='tab:orange')
        if not df['lux'].isna().all():
            ax2.plot(df['time'], df['lux'], color='tab:orange', label='Lux', linestyle='dashed', marker='^', markersize=3)
        ax2.tick_params(axis='y', labelcolor='tab:orange')

        # 解決 X 軸時間標籤過長或擠在一起的問題
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        fig.autofmt_xdate(rotation=45)

        plt.title(f"Plant Plot {suffix} (Last {len(logs)})")
        
        # 將圖表存入記憶體中 (RAM) 而不寫入硬碟
        buf = io.BytesIO()
        # 使用 bbox_inches='tight' 移除多餘空白點，並提高解析度以填滿容器
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', pad_inches=0.1)
        plt.close(fig)
        buf.seek(0)
        
        return buf
        
    except Exception as e:
        print(f"❌ [DataViz] 繪製趨勢圖失敗: {e}")
        return None

async def generate_metric_chart(metric: str) -> io.BytesIO | None:
    """回傳指定的指摽歷時資料漸層面積圖"""
    import matplotlib.dates as mdates
    from app.models import PlantLog, Plant
    
    plant = await Plant.first()
    if not plant:
        return None
    
    logs = await PlantLog.filter(plant=plant).order_by("-created_at").limit(60)
    if not logs:
        return None
    logs = sorted(logs, key=lambda x: x.created_at)
    
    data = []
    for log in logs:
        val = None
        if metric == "temp": val = log.temperature
        elif metric == "hum": val = log.humidity
        elif metric == "lux": val = log.lux
        
        data.append({
            "time": log.created_at,
            "val": val
        })
        
    df = pd.DataFrame(data)
    df['time'] = pd.to_datetime(df['time'])
    if df['time'].dt.tz is not None:
        df['time'] = df['time'].dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
    else:
        df['time'] = df['time'] + pd.Timedelta(hours=8)
        
    df = df.dropna(subset=['val'])
    if df.empty:
        return None

    colors = {"temp": "#ff9800", "hum": "#00bcd4", "lux": "#ffc107"}
    base_color = colors.get(metric, "#888888")

    fig, ax = plt.subplots(figsize=(6, 3))
    
    x = df['time']
    y = df['val']
    
    ax.plot(x, y, color=base_color, linewidth=2)
    ax.fill_between(x, y, y.min() * 0.9, color=base_color, alpha=0.3)
    ax.fill_between(x, y, y.min() * 0.9, color=base_color, alpha=0.1)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.grid(False, axis='y')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.autofmt_xdate(rotation=0)
    
    ax.tick_params(axis='y', colors=base_color, length=0)
    ax.tick_params(axis='x', colors="#aaaaaa", length=0, labelsize=8)
    
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf

async def generate_moisture_chart() -> io.BytesIO | None:
    """回傳土壤濕度折線圖，並疊加上澆水紀錄的水滴標記"""
    import matplotlib.dates as mdates
    from app.models import PlantLog, Plant, WateringLog
    
    plant = await Plant.first()
    if not plant:
        return None
    
    logs = await PlantLog.filter(plant=plant).order_by("-created_at").limit(60)
    if not logs:
        return None
    logs = sorted(logs, key=lambda x: x.created_at)
    
    start_time = logs[0].created_at
    end_time = logs[-1].created_at
    
    # 拉出這段時間內的澆水紀錄
    waterings = await WateringLog.filter(plant=plant, created_at__gte=start_time, created_at__lte=end_time).all()
    
    data = []
    for log in logs:
        data.append({"time": log.created_at, "val": log.soil_moisture})
        
    df = pd.DataFrame(data)
    df['time'] = pd.to_datetime(df['time'])
    
    # 轉換時區
    def to_taipei(dt_series):
        if dt_series.dt.tz is not None:
            return dt_series.dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        return dt_series + pd.Timedelta(hours=8)
        
    df['time'] = to_taipei(df['time'])
    df = df.dropna(subset=['val'])
    if df.empty:
        return None
    
    fig, ax = plt.subplots(figsize=(6, 3))
    x = df['time']
    y = df['val']
    
    ax.plot(x, y, color="#4caf50", linewidth=2)
    
    # 畫上澆水紀錄標籤
    from pandas import to_datetime
    for w in waterings:
        w_time = to_datetime(w.created_at)
        if w_time.tzinfo is not None:
            w_time = w_time.tz_convert('Asia/Taipei').tz_localize(None)
        else:
            w_time = w_time + pd.Timedelta(hours=8)
            
        # 找對應的 Y 軸高度 (最近的那個紀錄點高度)
        closest_idx = (df['time'] - w_time).abs().idxmin()
        w_y = df.loc[closest_idx, 'val']
        w_x = mdates.date2num(w_time)
        
        ax.vlines(x=w_time, ymin=w_y, ymax=y.max() + 5, color='gray', linestyle='dashed', alpha=0.5)
        
        label = "Watering" if w.source == "manual" else "Auto Water"
        ax.annotate(label, xy=(w_x, w_y), xytext=(0, 15), textcoords='offset points',
                    ha='center',
                    arrowprops=dict(facecolor='#00bcd4', shrink=0.05, width=1, headwidth=6),
                    fontsize=9, color="white", weight="bold",
                    bbox=dict(boxstyle="round,pad=0.3", fc="#00bcd4", ec="none", alpha=0.9))

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.grid(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.autofmt_xdate(rotation=0)
    
    ax.tick_params(axis='y', colors="#4caf50", length=0)
    ax.tick_params(axis='x', colors="#aaaaaa", length=0, labelsize=8)
    
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf
