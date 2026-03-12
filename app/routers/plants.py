import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.serial_reader import reader
from app.models import Plant
from app.auth import require_user_htmx
from datetime import datetime, date

router = APIRouter()
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

@router.get("/plants/sensors", response_class=HTMLResponse)
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


@router.post("/plants/water", response_class=HTMLResponse)
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

@router.get("/plants/settings", response_class=HTMLResponse)
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


@router.post("/plants/settings", response_class=HTMLResponse)
async def post_plant_settings(
    request: Request,
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

    # ── 取得或建立植物記錄 ──
    try:
        plant = await Plant.first()
        if plant:
            plant.nickname = nickname
            plant.species = species
            plant.planting_date = parsed_date
            await plant.save()
        else:
            plant = await Plant.create(
                nickname=nickname,
                species=species,
                planting_date=parsed_date,
            )
    except Exception as e:
        return HTMLResponse(
            content=f'<p style="color:var(--pico-del-color);">❌ 儲存失敗：{e}</p>'
        )

    # ── 回傳成功並導回首頁 ──
    import urllib.parse
    resp = HTMLResponse(content="設定成功，正在導向...")
    redirect_url = "/?msg=" + urllib.parse.quote("🌱 植物檔案設定成功！")
    resp.headers["HX-Redirect"] = redirect_url
    return resp


@router.post("/plants/upload-photo", response_class=HTMLResponse)
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
    # 我們回傳完整的預覽區塊，包含成功動畫與替換後的按鈕狀態
    return HTMLResponse(
        content=f'''
        <div id="photo-preview" class="photo-preview" style="position: relative;" hx-swap-oob="true">
            <img src="{relative_path}" alt="植物照片"
                 style="width: 100%; height: 100%; object-fit: cover; filter: brightness(0.8);">
            
            <!-- 成功動畫的勾勾 -->
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); 
                        color: #10B981; font-size: 4rem; animation: popIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
                        text-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            </div>
            
            <!-- 大約 2 秒後移除變暗效果與勾勾，並恢復原狀 -->
            <script>
                setTimeout(() => {{
                    const previewObj = document.getElementById("photo-preview");
                    if(previewObj) {{
                        const img = previewObj.querySelector("img");
                        const icon = previewObj.querySelector("div");
                        if(img) img.style.filter = "none";
                        if(icon) icon.remove();
                    }}
                }}, 2000);
            </script>
        </div>
        
        <!-- 更新按鈕文字為「更換照片」 -->
        <button type="button" id="upload-btn" class="outline secondary" style="width: auto; opacity: 0.8;" hx-swap-oob="true"
                onclick="document.getElementById('photo-input').click();">
            🔄 更換照片
        </button>

        <!-- Toast 訊息通知 -->
        <div id="photo-message" hx-swap-oob="true">
            <script>
                showToast("✅ 照片上傳成功", "success");
            </script>
        </div>
        '''
    )
