import re

with open("app/logic/dataviz.py", "r") as f:
    content = f.read()

# We want to replace everything from "async def generate_metric_chart" to the end of the file.
pattern = r"async def generate_metric_chart.*"
match = re.search(pattern, content, flags=re.DOTALL)
if match:
    prefix = content[:match.start()]
    new_content = prefix + """async def generate_metric_chart(metric: str) -> 'io.BytesIO | None':
    \"\"\"回傳指定的指摽歷時資料漸層面積圖\"\"\"
    import io
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from app.models import PlantLog, Plant
    
    plant = await Plant.first()
    if not plant: return None
    
    logs = await PlantLog.filter(plant=plant).order_by("-created_at").limit(60)
    if not logs: return None
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
    if df.empty: return None

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

async def generate_moisture_chart() -> 'io.BytesIO | None':
    \"\"\"回傳土壤濕度折線圖，並疊加上澆水紀錄的水滴標記\"\"\"
    import io
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from app.models import PlantLog, Plant, WateringLog
    
    plant = await Plant.first()
    if not plant: return None
    
    logs = await PlantLog.filter(plant=plant).order_by("-created_at").limit(60)
    if not logs: return None
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
    if df.empty: return None
    
    fig, ax = plt.subplots(figsize=(6, 3))
    x = df['time']
    y = df['val']
    
    ax.plot(x, y, color="#4caf50", linewidth=2)
    
    # 畫上澆水紀錄標籤
    for w in waterings:
        # Timezone conversion for single scalar
        w_time = pd.to_datetime(w.created_at)
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
"""
    with open("app/logic/dataviz.py", "w") as f:
        f.write(new_content)
    print("Successfully replaced dataviz.py")
else:
    print("Could not find generation block in dataviz.py")

