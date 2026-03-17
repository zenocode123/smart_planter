import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
from datetime import datetime
import matplotlib

# 使用非互動式 backend 避免在樹莓派背景執行時出現 GUI 錯誤
matplotlib.use('Agg')

# 定義圖片儲存目錄
PLOT_DIR = Path("app/static/plots")

async def generate_history_plot(limit: int = 50, plant_id: int = None) -> str | None:
    """
    從資料庫中撈取最近 `limit` 筆的 PlantLog (可選指定 plant_id)，
    繪製趨勢圖並存檔。
    """
    from app.models import PlantLog
    try:
        PLOT_DIR.mkdir(parents=True, exist_ok=True)
        suffix = f"_{plant_id}" if plant_id else ""
        file_path = PLOT_DIR / f"history_chart{suffix}.png"
        
        # 取得紀錄
        query = PlantLog.all().order_by("-created_at")
        if plant_id:
            query = query.filter(plant_id=plant_id)
            
        logs = await query.limit(limit)
        
        if not logs:
            print(f"⚠️ [DataViz] 植物 {plant_id} 尚無資料，跳過繪圖。")
            return None
            
        logs = sorted(logs, key=lambda x: x.created_at)
        
        # 轉換為 Pandas DataFrame
        data = []
        for log in logs:
            data.append({
                "time": log.created_at,
                "temperature": log.temperature,
                "humidity": log.humidity,
                "moisture": log.soil_moisture,
                "lux": log.lux
            })
            
        df = pd.DataFrame(data)
        
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

        ax2 = ax1.twinx()  
        ax2.set_ylabel('Lux', color='tab:orange')
        if not df['lux'].isna().all():
            ax2.plot(df['time'], df['lux'], color='tab:orange', label='Lux', linestyle='dashed', marker='^', markersize=3)
        ax2.tick_params(axis='y', labelcolor='tab:orange')

        plt.title(f"Plant Plot {suffix} (Last {len(logs)})")
        fig.tight_layout()
        
        plt.savefig(str(file_path), dpi=100)
        plt.close(fig)
        
        return f"/static/plots/history_chart{suffix}.png"
        
    except Exception as e:
        print(f"❌ [DataViz] 繪製趨勢圖失敗: {e}")
        return None
