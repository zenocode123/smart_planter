import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.mqtt_client import mqtt_client as reader
from app.models import Plant
from app.auth import require_user_htmx
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
    """供 HTMX 定期調用的感測器數據片段"""
    latest_data = reader.get_data()
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
    """觸發 ESP32 執行澆水動作"""
    # 2. 發送指令給 ESP32
    await reader.send_command("water", {"seconds": WATERING_SECONDS})

    # 3. 無論成功與否，都回傳最新的感測器片段 (讓 UI 根據真實狀態更新)
    # 如果指令發送成功，ESP32 應該會很快回傳 watering: true，從而顯示彈窗
    return await get_sensor_data(request)


# ───────────────────────────────────────
# UC03：植物檔案設定
# ───────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def get_plant_settings(request: Request, user=Depends(require_user_htmx)) -> HTMLResponse:
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


async def _update_personality_task(plant_id: int, species: str, nickname: str):
    """背景任務：生成 AI 人格並更新資料庫"""
    from app.ai.personality import generate_personality
    from app.models import Plant
    
    personality = await generate_personality(species=species, nickname=nickname)
    if personality:
        plant = await Plant.get_or_none(id=plant_id)
        if plant:
            plant.ai_personality = personality
            await plant.save()

@router.post("/settings", response_class=HTMLResponse)
async def post_plant_settings(
    request: Request,
    background_tasks: BackgroundTasks,
    user=Depends(require_user_htmx),
    nickname: str = Form(...),
    species: str = Form(...),
    planting_date: str = Form(""),
) -> HTMLResponse:
    """[UC03] 儲存植物檔案設定"""
    # ── 資料驗證 ──
    errors: list[str] = []
    nickname = nickname.strip()
    species = species.strip()

    if not nickname:
        errors.append("植物暱稱為必填欄位")
    if not species:
        errors.append("植物品種為必填欄位")

    if errors:
        error_html = "".join(
            f'<p style="color:var(--pico-del-color); margin:0.25rem 0;">❌ {e}</p>'
            for e in errors
        )
        return HTMLResponse(content=error_html)

    # ── 解析日期 ──
    parsed_date: date | None = None
    if planting_date:
        try:
            parsed_date = date.fromisoformat(planting_date)
        except ValueError:
            return HTMLResponse(
                content='<p style="color:var(--pico-del-color);">❌ 日期格式錯誤</p>'
            )

    # ── 取得或建立植物記錄（偵測品種變更）──
    species_changed: bool = False
    is_new_plant: bool = False
    try:
        plant = await Plant.first()
        if plant:
            # 記錄舊品種以偵測變更
            old_species: str = plant.species
            species_changed = (old_species != species)
            plant.nickname = nickname
            plant.species = species
            plant.planting_date = parsed_date
            await plant.save()
        else:
            is_new_plant = True
            plant = await Plant.create(
                nickname=nickname,
                species=species,
                planting_date=parsed_date,
            )
    except Exception as e:
        return HTMLResponse(
            content=f'<p style="color:var(--pico-del-color);">❌ 儲存失敗：{e}</p>'
        )

    # ── [UC03 Step 6] AI 人格初始化（改為背景任務）──
    personality_msg: str = ""
    if species_changed or is_new_plant:
        # 使用 BackgroundTasks 避免阻塞主流程 (解決 Ollama 500/Timeout 問題)
        background_tasks.add_task(_update_personality_task, plant.id, species, nickname)
        personality_msg = "（AI正在進化中...）"

    # ── 回傳成功並導回首頁 ──
    import urllib.parse
    resp = HTMLResponse(content="設定成功，正在導向...")
    flash_msg: str = f"🌱 植物檔案儲存成功！{personality_msg}"
    redirect_url = "/?msg=" + urllib.parse.quote(flash_msg)
    resp.headers["HX-Redirect"] = redirect_url
    return resp



@router.post("/upload-photo", response_class=HTMLResponse)
async def upload_plant_photo(
    request: Request,
    user=Depends(require_user_htmx),
    photo: UploadFile = File(...),
) -> HTMLResponse:
    """[UC03] 上傳植物照片"""
    # ── 驗證檔案類型 ──
    ext = Path(photo.filename).suffix.lower() if photo.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return HTMLResponse(
            content='<p style="color:var(--pico-del-color);">❌ 照片格式錯誤，僅支援 JPG、PNG、WebP</p>',
        )

    # ── 驗證檔案大小 ──
    contents = await photo.read()
    if len(contents) > MAX_FILE_SIZE:
        return HTMLResponse(
            content='<p style="color:var(--pico-del-color);">❌ 檔案過大，上限為 5MB</p>',
        )

    # ── 儲存檔案 ──
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"plant_{uuid.uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(contents)

    # ── 更新資料庫 ──
    relative_path = f"/static/uploads/plants/{filename}"
    plant = await Plant.first()
    if plant:
        # 刪除舊照片
        if plant.photo_path:
            old_file = Path("app" + plant.photo_path)
            if old_file.exists():
                old_file.unlink()
        plant.photo_path = relative_path
        await plant.save()
    else:
        await Plant.create(
            nickname="我的植物",
            species="未設定",
            photo_path=relative_path,
        )

    # ── 回傳更新後的照片預覽片段 ──
    # 使用獨立範本回傳 OOB 更新，保持 Python 代碼純淨
    return templates.TemplateResponse(
        "photo_upload_fragment.html",
        {
            "request": request,
            "photo_url": relative_path,
        },
    )

