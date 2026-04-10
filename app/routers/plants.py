import os
import uuid
from pathlib import Path
from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form,
    UploadFile,
    File,
    BackgroundTasks,
    Response,
)
from fastapi.responses import HTMLResponse, JSONResponse
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


@router.get("/watering-status", response_class=JSONResponse)
async def watering_status() -> JSONResponse:
    """超輕量端點：只回傳澆水狀態，供前端高頻輪詢使用 (不讀取耗時資料庫連線或重繪 DOM)"""
    # 使用 Plant.first().id（純整數），不用 latest_log.plant_id（Tortoise FK 欄位型別不穩定）
    plant = await Plant.first()
    watering = False
    timestamp = 0
    if plant:
        watering = bool(mqtt_service.latest_watering.get(plant.id, False))
        timestamp = mqtt_service.latest_update_time.get(plant.id, 0)
    return JSONResponse({"watering": watering, "timestamp": timestamp})


@router.get("/sensors", response_class=HTMLResponse)
async def get_sensor_data(request: Request) -> HTMLResponse:
    """供 HTMX 定期調用的感測器數據片段 (從資料庫獲取最新一筆)"""
    latest_log = await PlantLog.all().order_by("-created_at").first()

    # 透過時間差判斷最近是否活躍連線 (120 秒內有真實 MQTT 資料)
    import time
    status = "disconnected"
    if latest_log:
        last_update = mqtt_service.latest_update_time.get(latest_log.plant_id, 0)
        if last_update > 0 and (time.time() - last_update) < 120:
            status = "connected"

    water_empty = False
    watering = False
    if latest_log:
        water_empty = mqtt_service.latest_water_empty.get(latest_log.plant_id, False)
        watering = mqtt_service.latest_watering.get(latest_log.plant_id, False)

    latest_data = {
        "status": status,
        "watering": watering,
        "water_empty": water_empty,
        "temp": latest_log.temperature if latest_log else None,
        "hum": latest_log.humidity if latest_log else None,
        "moisture": latest_log.soil_moisture if latest_log else None,
        "lux": latest_log.lux if latest_log else None,
    }
    update_time_str = "--"
    if latest_log:
        last_update = mqtt_service.latest_update_time.get(latest_log.plant_id, 0)
        if last_update > 0:
            update_time_str = datetime.fromtimestamp(last_update).strftime("%Y/%m/%d %H:%M:%S")
        else:
            dt = latest_log.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            update_time_str = dt.astimezone().strftime("%Y/%m/%d %H:%M:%S")
    return templates.TemplateResponse(
        "sensor_fragment.html",
        {
            "request": request,
            "data": latest_data,
            "update_time": update_time_str,
            "interval": UPDATE_INTERVAL,
        },
    )


@router.post("/water", response_class=Response)
async def water_plant(
    request: Request, force: bool = False, user=Depends(require_user_htmx)
) -> Response:
    """觸發 ESP32 執行澆水動作 (透過 MQTT)，並加入硬體異常數值防呆"""
    plant = await Plant.first()
    latest_log = await PlantLog.all().order_by("-created_at").first()

    # 1. 網路斷線防護 (超過 65 秒未收到 MQTT 資料，視為設備離線，拒絕發送指令)
    import time
    if latest_log:
        last_update = mqtt_service.latest_update_time.get(latest_log.plant_id, 0)
        diff_seconds = time.time() - last_update if last_update > 0 else 999
        if diff_seconds > 65:
            return templates.TemplateResponse(
                "error_modal.html",
                {
                    "request": request,
                    "icon": "❌",
                    "title": "裝置已離線",
                    "message": "系統偵測到裝置已離線 (網路延遲超過 65 秒)，為確保安全，已攔截此澆水指令。請檢查硬體連線後重試！",
                },
            )

    # 2. 缺水阻斷 (不分是否 Force，沒水就是不能澆)
    if latest_log and mqtt_service.latest_water_empty.get(latest_log.plant_id, False):
        return templates.TemplateResponse(
            "error_modal.html",
            {
                "request": request,
                "icon": "💧",
                "title": "儲水箱見底",
                "message": "儲水箱已經見底，嚴禁啟動抽水馬達，請先補水！",
            },
        )

    # 3. 實體感測器異常防呆 (例如溫度破百)
    warnings = []
    if not latest_log:
        warnings.append("尚未收到任何來自 ESP32 的感測器數據包 (通訊異常)。")
    else:
        t = latest_log.temperature
        if t is None:
            warnings.append("尚未抓取到『溫度』數據 (Sensor 無回應)。")
        elif t < -20 or t > 60:
            warnings.append(f"溫度數值明顯異常 ({t}℃)，硬體可能短路或接線錯誤。")

        h = latest_log.humidity
        if h is None:
            warnings.append("尚未抓取到『濕度』數據 (Sensor 無回應)。")
        elif h < 0 or h > 100:
            warnings.append(f"濕度數值不合理 ({h}%)，感測器可能故障。")

        s = latest_log.soil_moisture
        if s is None:
            warnings.append("尚未抓取到『土壤濕度』數據。")
        elif s < 0 or s > 100:
            warnings.append(f"土壤濕度超出正常範圍 ({s}%)，ADC 電壓讀取可能失準。")

        l = latest_log.lux
        if l is None:
            warnings.append("尚未抓取到『環境光照』數據。")
        elif l < 0 or l > 100000:
            warnings.append(f"光照亮度異常 ({l} lux)，光線感測器可能損壞。")

    if warnings and not force:
        return templates.TemplateResponse(
            "water_warning_modal.html", {"request": request, "warnings": warnings}
        )

    # 4a. 如果是異常但被強制啟動 -> 跳過 AI 直接以安全水量 (1.0s) 給水
    if force:
        import time

        cmd_time = time.time()
        if plant and plant.mqtt_topic_id and mqtt_service.client:
            topic = f"planter/{plant.mqtt_topic_id}/cmd"
            mqtt_service.client.publish(
                topic, json.dumps({"action": "water", "duration": 1.0})
            )
        # 回傳 204，前端 hx-on::after-request 收到後會 dispatch start-watering-client
        resp = Response(status_code=204)
        resp.headers["X-Command-Time"] = str(cmd_time)
        return resp

    # 4b. 數據無異常 -> 呼叫 AI 諮詢（加上 timeout 保護避免卡死）
    advice = await _get_watering_advice(plant, latest_log)

    # 5. 回傳 AI 建議的確認彈窗
    return templates.TemplateResponse(
        "ai_watering_confirm.html",
        {"request": request, "advice": advice},
    )


# ───────────────────────────────────────
# AI 澆水諮詢輔助函式
# ───────────────────────────────────────
import asyncio as _asyncio
import os as _os
from openai import OpenAI as _OpenAI
from app.ai.prompts import WATERING_ADVICE_PROMPT, with_retry_sync, robust_json_parse


@with_retry_sync(max_retries=2)
def _call_ai_sync_advice(prompt: str) -> str:
    api_key = _os.getenv("NVIDIA_NIM_API_KEY")
    base_url = _os.getenv("NVIDIA_NIM_BASE_URL")
    model = _os.getenv("NVIDIA_MODEL_NAME")
    if not api_key or not base_url:
        raise ValueError("NVIDIA API 未設定")
    client = _OpenAI(base_url=base_url, api_key=api_key)
    res = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=80,
    )
    return res.choices[0].message.content.strip()


async def _get_watering_advice(plant, latest_log) -> dict:
    species = plant.species if plant else "未知"
    fallback = {
        "recommend": True,
        "reason": "AI 未回覆，請自行判斷是否澆水。",
        "temp": latest_log.temperature if latest_log else None,
        "humidity": latest_log.humidity if latest_log else None,
        "moisture": latest_log.soil_moisture if latest_log else None,
        "lux": latest_log.lux if latest_log else None,
        "species": species,
    }
    if not latest_log or not _os.getenv("NVIDIA_NIM_API_KEY"):
        return fallback

    prompt = WATERING_ADVICE_PROMPT.format(
        species=species,
        temp=latest_log.temperature if latest_log.temperature is not None else "N/A",
        humidity=latest_log.humidity if latest_log.humidity is not None else "N/A",
        moisture=latest_log.soil_moisture
        if latest_log.soil_moisture is not None
        else "N/A",
        lux=latest_log.lux if latest_log.lux is not None else "N/A",
    )
    try:
        loop = _asyncio.get_event_loop()
        raw = await _asyncio.wait_for(
            loop.run_in_executor(None, _call_ai_sync_advice, prompt), timeout=6.0
        )
        parsed = robust_json_parse(raw)
        fallback["recommend"] = bool(parsed.get("recommend", True))
        fallback["reason"] = parsed.get("reason", "AI 判定完成")
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"AI 諮詢失敗: {e}")
        fallback["reason"] = f"AI 回覆超時或錯誤，請自行作主。"
    return fallback


# ───────────────────────────────────────
# 確認澆水端點（來自 AI 確認彈窗）
# ───────────────────────────────────────
@router.post("/water/confirm", response_class=Response)
async def confirm_water_plant(
    request: Request, user=Depends(require_user_htmx)
) -> Response:
    """彈窗按下確定後的最終給水端點 (動態計算水量)"""
    plant = await Plant.first()
    latest_log = await PlantLog.all().order_by("-created_at").first()

    if plant and mqtt_service.latest_water_empty.get(plant.id, False):
        return templates.TemplateResponse(
            "error_modal.html",
            {
                "request": request,
                "icon": "💧",
                "title": "儲水箱見底",
                "message": "儲水箱見底，取消灌溉！",
            },
            status_code=409,
        )

    duration = 1.0
    if latest_log and latest_log.soil_moisture is not None:
        soil = latest_log.soil_moisture
        if soil < 20:
            duration = 2.5
        elif soil < 40:
            duration = 1.5
        elif soil < 60:
            duration = 0.8
        else:
            duration = 0.5  # 土壤濕的但仍強拉給水 -> 最少量防呆

    import time

    cmd_time = time.time()
    if plant and plant.mqtt_topic_id and mqtt_service.client:
        topic = f"planter/{plant.mqtt_topic_id}/cmd"
        mqtt_service.client.publish(
            topic, json.dumps({"action": "water", "duration": duration})
        )

        # [UC12] 紀錄手動澆水行為
        try:
            from app.models import WateringLog

            await WateringLog.create(plant=plant, source="manual", duration=duration)
        except Exception as e:
            print(f"寫入 WateringLog 失敗: {e}")

    resp = Response(status_code=204)
    resp.headers["X-Command-Time"] = str(cmd_time)
    return resp


# ───────────────────────────────────────
# UC03：植物檔案設定
# ───────────────────────────────────────

from app.schemas.plant import PlantCreate
from app.ai.personality import generate_personality


async def _update_personality_task(plant_id: int, species: str, nickname: str) -> None:
    """背景任務：呼叫 AI 生成人格描述並儲存至資料庫"""
    try:
        personality = await generate_personality(species=species, nickname=nickname)
        if personality:
            plant_obj = await Plant.get_or_none(id=plant_id)
            if plant_obj:
                plant_obj.ai_personality = personality
                await plant_obj.save()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).error(f"❌ AI 人格背景更新失敗: {exc}")


# ── UC03：植物檔案設定 ──


@router.get("/profile", response_class=HTMLResponse)
async def get_plant_profile(
    request: Request, user=Depends(require_user_htmx)
) -> HTMLResponse:
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
            planting_date=parsed_date,
        )
    except Exception as e:
        # 若驗證失敗，回傳 HTMX 錯誤訊息
        return HTMLResponse(
            content=f'<p style="color:var(--pico-del-color);">❌ 驗證失敗: {str(e)}</p>'
        )

    # ── 取得或建立植物記錄（偵測品種變更）──
    species_changed: bool = False
    is_new_plant: bool = False
    try:
        plant = await Plant.first()
        if plant:
            species_changed = plant.species != plant_in.species
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
        return HTMLResponse(
            content=f'<p style="color:var(--pico-del-color);">❌ 儲存失敗：{e}</p>'
        )

    # ── [UC03 Step 6] AI 人格初始化（背景任務）──
    if species_changed or is_new_plant:
        background_tasks.add_task(
            _update_personality_task, plant.id, plant.species, plant.nickname
        )

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
        return HTMLResponse(
            content='<p style="color:var(--pico-del-color);">❌ 格式錯誤</p>'
        )

    contents = await photo.read()
    if len(contents) > MAX_FILE_SIZE:
        return HTMLResponse(
            content='<p style="color:var(--pico-del-color);">❌ 檔案過大</p>'
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"plant_{uuid.uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(contents)

    relative_path = f"/static/uploads/plants/{filename}"
    plant = await Plant.first()
    if plant:
        if plant.photo_path:
            old_file = Path("app" + plant.photo_path)
            if old_file.exists():
                old_file.unlink()
        plant.photo_path = relative_path
        await plant.save()
    else:
        await Plant.create(
            nickname="我的植物", species="未設定", photo_path=relative_path
        )

    return templates.TemplateResponse(
        "photo_upload_fragment.html", {"request": request, "photo_url": relative_path}
    )


@router.get("/fragments/modal-chart")
async def get_modal_chart_fragment(metric: str):
    """回傳 HTMX Modal 浮窗 HTML (包含圖表圖片網址)"""
    metric_map = {
        "temp": "🌡️ 溫度",
        "hum": "💧 濕度",
        "moisture": "🌱 土壤濕度",
        "lux": "☀️ 光照",
    }
    title = metric_map.get(metric, "感測數值")

    html = f"""
    <dialog id="chart-modal" open>
        <article style="max-width: 650px; overflow-x: hidden;">
            <header style="display: flex; align-items: center; justify-content: space-between;">
                <strong style="margin: 0;">{title} 歷史趨勢圖</strong>
                <button aria-label="Close" rel="prev" onclick="this.closest('dialog').removeAttribute('open'); document.getElementById('metric-modal-container').innerHTML=''" style="margin: 0; outline: none; box-shadow: none;"></button>
            </header>
            <div style="text-align: center; padding-top: 1rem;">
                <img class="img-fluid fade-in" src="/plants/plots/modal/{metric}.png" alt="{title} 趨勢圖" style="max-width: 100%; height: auto;" />
            </div>
        </article>
    </dialog>
    """
    return HTMLResponse(content=html)


@router.get("/plots/modal/{metric}.png")
async def get_modal_chart_image(metric: str):
    """回傳專為 Modal 設計的視覺化極簡圖表 (模擬資料)"""
    from app.logic.dataviz import generate_metric_chart, generate_moisture_chart
    from fastapi import Response, HTTPException

    if metric == "moisture":
        buf = await generate_moisture_chart()
    else:
        buf = await generate_metric_chart(metric)

    if not buf:
        raise HTTPException(status_code=404, detail="Plot generation failed")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.get("/plots/{plant_id}/chart.png")
async def get_plant_history_chart(plant_id: int, end_timestamp: float = None):
    """即時自資料庫撈取資料，並在 RAM 中繪製回傳 PNG，完全不寫入硬碟以保護 SD 卡"""
    from app.logic.dataviz import generate_history_plot
    from fastapi import Response, HTTPException

    buf = await generate_history_plot(limit=50, plant_id=plant_id, end_timestamp=end_timestamp)
    if not buf:
        raise HTTPException(status_code=404, detail="Plot generation failed or no data")
    return Response(content=buf.getvalue(), media_type="image/png")




# ── UC10：定時排程紀錄展示 ──


@router.get("/logs/latest", response_class=HTMLResponse)
async def get_latest_log(
    request: Request, user=Depends(require_user_htmx)
) -> HTMLResponse:
    """[UC10] 供 HTMX 調用的最新排程紀錄與歷史圖表片段
    ⚠️ 只抓有 ai_analysis 的健檢 log，排除 MQTT 即時傳入的純感測數值 log
    """
    from app.models import PlantLog

    latest_log = (
        await PlantLog.filter(ai_analysis__isnull=False)
        .exclude(ai_analysis="")
        .order_by("-created_at")
        .first()
    )
    return templates.TemplateResponse(
        "log_fragment.html", {"request": request, "log": latest_log}
    )


@router.get("/reports", response_class=HTMLResponse)
async def get_reports_page(
    request: Request, user=Depends(require_user_htmx)
) -> HTMLResponse:
    from app.models import PlantLog

    # 只列出有 AI 分析的健檢紀錄，排除 MQTT 即時傳入的純感測 log
    logs = (
        await PlantLog.filter(ai_analysis__isnull=False)
        .exclude(ai_analysis="")
        .order_by("-created_at")
    )
    latest_log = logs[0] if logs else None
    return templates.TemplateResponse(
        "reports.html",
        {"request": request, "user": user, "logs": logs, "selected_log": latest_log},
    )


@router.get("/reports/log/{log_id}", response_class=HTMLResponse)
async def get_report_detail(
    request: Request, log_id: int, user=Depends(require_user_htmx)
) -> HTMLResponse:
    from app.models import PlantLog

    log = await PlantLog.get_or_none(id=log_id)
    return templates.TemplateResponse(
        "log_fragment.html", {"request": request, "log": log}
    )


@router.get("/reports/log/{log_id}/chart.png")
async def get_report_log_chart(log_id: int):
    """回傳特定 PlantLog 紀錄的趨勢圖快照（從 chart_blob 讀取）"""
    from app.models import PlantLog
    from fastapi import HTTPException

    log = await PlantLog.get_or_none(id=log_id)
    if not log or not log.chart_blob:
        raise HTTPException(status_code=404, detail="此紀錄沒有趨勢圖快照")
    return Response(content=bytes(log.chart_blob), media_type="image/png")


@router.get("/reports/log/{log_id}/photo.jpg")
async def get_report_log_photo(log_id: int):
    """回傳特定 PlantLog 紀錄的植物照片快照（從 photo_blob 讀取）"""
    from app.models import PlantLog
    from fastapi import HTTPException

    log = await PlantLog.get_or_none(id=log_id)
    if not log or not log.photo_blob:
        raise HTTPException(status_code=404, detail="此紀錄沒有照片快照")
    return Response(content=bytes(log.photo_blob), media_type="image/jpeg")


@router.post("/reports/trigger", response_class=HTMLResponse)
async def trigger_manual_report(
    request: Request, background_tasks: BackgroundTasks, user=Depends(require_user_htmx)
) -> HTMLResponse:
    from app.scheduler import daily_plant_routine

    background_tasks.add_task(daily_plant_routine)

    content = """
    <div style="text-align: center; color: var(--pico-primary); padding: 2rem; border: 1px dashed var(--pico-primary); border-radius: 8px; margin-top: 1.5rem;">
        ⚙️ 排程已啟動（AI 正在分析數據與撰寫電子郵件中）...
        <p style="font-size: 0.85rem; margin-top: 1rem; opacity: 0.8;">由於呼叫 AI 與寄信需要時間，頁面將於 <strong>12 秒後</strong> 自動更新以顯示最新報表。</p>
        <progress indeterminate style="margin-top: 1rem; max-width: 200px;"></progress>
    </div>
    <!-- 遵守 HTMX 規範，使用延遲觸發器進行局部或全局刷新 -->
    <div hx-get="/reports" hx-trigger="load delay:12s" hx-target="body"></div>
    """
    return HTMLResponse(content=content)
