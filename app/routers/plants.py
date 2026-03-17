import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.models import Plant, PlantLog
from app.auth import require_user_htmx
from app.logic.mqtt_service import mqtt_service
import json
from datetime import datetime, date

router = APIRouter(prefix="/plants")
templates = Jinja2Templates(directory="app/templates")

UPDATE_INTERVAL = int(os.getenv("SYSTEM_UPDATE_INTERVAL", "5"))
WATERING_SECONDS = int(os.getenv("DEFAULT_WATERING_SECONDS", "3"))

# 照片上傳設定
UPLOAD_DIR = Path("app/static/uploads/plants")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


# ───────────────────────────────────────
# 既有路由：感測器資料 & 澆水
# ───────────────────────────────────────

@router.get("/sensors", response_class=HTMLResponse)
async def get_sensor_data(request: Request) -> HTMLResponse:
    """供 HTMX 定期調用的感測器數據片段 (從資料庫獲取最新一筆)"""
    latest_log = await PlantLog.all().order_by("-created_at").first()
    
    # 透過時間差判斷最近是否活躍連線 (120 秒內有資料)
    status = "disconnected"
    if latest_log:
        diff_seconds = (datetime.now(latest_log.created_at.tzinfo) - latest_log.created_at).total_seconds()
        if diff_seconds < 120:
            status = "connected"

    latest_data = {
        "status": status,
        "watering": False,
        "temp": latest_log.temperature if latest_log else None,
        "hum": latest_log.humidity if latest_log else None,
        "moisture": latest_log.soil_moisture if latest_log else None,
        "lux": latest_log.lux if latest_log else None,
    }
    now = datetime.now().strftime("%H:%M:%S")
    return templates.TemplateResponse(
        "sensor_fragment.html",
        {
            "request": request,
            "data": latest_data,
            "update_time": now,
            "interval": UPDATE_INTERVAL,
        },
    )


@router.post("/water", response_class=HTMLResponse)
async def water_plant(request: Request, user=Depends(require_user_htmx)) -> HTMLResponse:
    """觸發 ESP32 執行澆水動作 (透過 MQTT)，並透過邏輯判斷秒數"""
    plant = await Plant.first()
    latest_log = await PlantLog.all().order_by("-created_at").first()
    
    # 動態給水邏輯：依照土壤濕度 (0~100) 給予不同秒數，最多不超過 3 秒
    duration = 1.0 # 預設瞎猜值
    if latest_log and latest_log.soil_moisture is not None:
        soil = latest_log.soil_moisture
        if soil < 20: 
            duration = 2.5
        elif soil < 40:
            duration = 1.5
        elif soil < 60:
            duration = 0.8
        else:
            duration = 0.0 # 拒絕澆水
            
    if duration > 0 and plant and plant.mqtt_topic_id and mqtt_service.client:
        topic = f"planter/{plant.mqtt_topic_id}/cmd"
        
        # 1. 發送澆水指令 (ESP32 會自動顯示 watering 表情)
        payload = {"action": "water", "duration": duration}
        mqtt_service.client.publish(topic, json.dumps(payload))
        
        # 提醒：若太過潮濕被拒絕，亦可在此發送 emotion: angry 等指令 (擴充用)
    
    return await get_sensor_data(request)


# ───────────────────────────────────────
# UC03：植物檔案設定
# ───────────────────────────────────────

from app.schemas.plant import PlantCreate

# ── UC03：植物檔案設定 ──

@router.get("/profile", response_class=HTMLResponse)
async def get_plant_profile(request: Request, user=Depends(require_user_htmx)) -> HTMLResponse:
    """[UC03] 顯示植物檔案設定頁面"""
    plant = await Plant.first()
    return templates.TemplateResponse(
        "plant_settings.html",
        {
            "request": request,
            "user": user,
            "plant": plant,
        },
    )

@router.post("/profile", response_class=HTMLResponse)
async def post_plant_profile(
    request: Request,
    background_tasks: BackgroundTasks,
    user=Depends(require_user_htmx),
    nickname: str = Form(...),
    species: str = Form(...),
    planting_date: str = Form(""),
) -> HTMLResponse:
    """[UC03] 儲存植物檔案設定"""
    
    # ── 使用 Pydantic 進行資料驗證 ──
    try:
        # 處理日期字串轉為 date 物件
        parsed_date = None
        if planting_date.strip():
            parsed_date = date.fromisoformat(planting_date)
            
        plant_in = PlantCreate(
            nickname=nickname.strip(),
            species=species.strip(),
            planting_date=parsed_date
        )
    except Exception as e:
        # 若驗證失敗，回傳 HTMX 錯誤訊息
        return HTMLResponse(content=f'<p style="color:var(--pico-del-color);">❌ 驗證失敗: {str(e)}</p>')

    # ── 取得或建立植物記錄（偵測品種變更）──
    species_changed: bool = False
    is_new_plant: bool = False
    try:
        plant = await Plant.first()
        if plant:
            species_changed = (plant.species != plant_in.species)
            plant.nickname = plant_in.nickname
            plant.species = plant_in.species
            plant.planting_date = plant_in.planting_date
            await plant.save()
        else:
            is_new_plant = True
            plant = await Plant.create(**plant_in.dict())
            # 確保新植物能與預設的 ESP32 對接
            plant.mqtt_topic_id = "p001"
            await plant.save()
    except Exception as e:
        return HTMLResponse(content=f'<p style="color:var(--pico-del-color);">❌ 儲存失敗：{e}</p>')

    # ── [UC03 Step 6] AI 人格初始化（背景任務）──
    if species_changed or is_new_plant:
        background_tasks.add_task(_update_personality_task, plant.id, plant.species, plant.nickname)

    import urllib.parse
    flash_msg = f"🌱 植物檔案儲存成功！{'（AI 正在進化中...請稍候）' if (species_changed or is_new_plant) else ''}"
    encoded_msg = urllib.parse.quote(flash_msg)
    
    # 嚴格遵守 HTMX 規範，使用 Header 驅動前端重新導向
    content = '<div style="color:var(--pico-ins-color); text-align:center;">設定成功！正在為您跳轉...</div>'
    response = HTMLResponse(content=content)
    response.headers["HX-Redirect"] = f"/?msg={encoded_msg}"
    return response

@router.post("/photo", response_class=HTMLResponse)
async def upload_plant_photo(
    request: Request,
    user=Depends(require_user_htmx),
    photo: UploadFile = File(...),
) -> HTMLResponse:
    """[UC03] 上傳植物照片"""
    # 驗證邏輯保持不變，路徑更新為 /photo
    ext = Path(photo.filename).suffix.lower() if photo.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return HTMLResponse(content='<p style="color:var(--pico-del-color);">❌ 格式錯誤</p>')

    contents = await photo.read()
    if len(contents) > MAX_FILE_SIZE:
        return HTMLResponse(content='<p style="color:var(--pico-del-color);">❌ 檔案過大</p>')

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"plant_{uuid.uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(contents)

    relative_path = f"/static/uploads/plants/{filename}"
    plant = await Plant.first()
    if plant:
        if plant.photo_path:
            old_file = Path("app" + plant.photo_path)
            if old_file.exists(): old_file.unlink()
        plant.photo_path = relative_path
        await plant.save()
    else:
        await Plant.create(nickname="我的植物", species="未設定", photo_path=relative_path)

    return templates.TemplateResponse("photo_upload_fragment.html", {"request": request, "photo_url": relative_path})


# ── UC10：定時排程紀錄展示 ──

@router.get("/logs/latest", response_class=HTMLResponse)
async def get_latest_log(request: Request, user=Depends(require_user_htmx)) -> HTMLResponse:
    """[UC10] 供 HTMX 調用的最新排程紀錄與歷史圖表片段"""
    from app.models import PlantLog
    latest_log = await PlantLog.all().order_by("-created_at").first()
    return templates.TemplateResponse("log_fragment.html", {"request": request, "log": latest_log})

@router.get("/reports", response_class=HTMLResponse)
async def get_reports_page(request: Request, user=Depends(require_user_htmx)) -> HTMLResponse:
    from app.models import PlantLog
    logs = await PlantLog.all().order_by("-created_at")
    latest_log = logs[0] if logs else None
    return templates.TemplateResponse("reports.html", {"request": request, "user": user, "logs": logs, "selected_log": latest_log})

@router.get("/reports/log/{log_id}", response_class=HTMLResponse)
async def get_report_detail(request: Request, log_id: int, user=Depends(require_user_htmx)) -> HTMLResponse:
    from app.models import PlantLog
    log = await PlantLog.get_or_none(id=log_id)
    return templates.TemplateResponse("log_fragment.html", {"request": request, "log": log})

@router.post("/reports/trigger", response_class=HTMLResponse)
async def trigger_manual_report(request: Request, background_tasks: BackgroundTasks, user=Depends(require_user_htmx)) -> HTMLResponse:
    from app.scheduler import daily_plant_routine
    background_tasks.add_task(daily_plant_routine)
    
    content = '''
    <div style="text-align: center; color: var(--pico-primary); padding: 2rem; border: 1px dashed var(--pico-primary); border-radius: 8px; margin-top: 1.5rem;">
        ⚙️ 排程已啟動（AI 正在分析數據與撰寫電子郵件中）...
        <p style="font-size: 0.85rem; margin-top: 1rem; opacity: 0.8;">由於呼叫 AI 與寄信需要時間，頁面將於 <strong>12 秒後</strong> 自動更新以顯示最新報表。</p>
        <progress indeterminate style="margin-top: 1rem; max-width: 200px;"></progress>
    </div>
    <!-- 遵守 HTMX 規範，使用延遲觸發器進行局部或全局刷新 -->
    <div hx-get="/reports" hx-trigger="load delay:12s" hx-target="body"></div>
    '''
    return HTMLResponse(content=content)



