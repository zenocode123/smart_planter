from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.serial_reader import reader
from datetime import datetime
from app.auth import require_user_htmx
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

UPDATE_INTERVAL = int(os.getenv("SYSTEM_UPDATE_INTERVAL", "5"))
WATERING_SECONDS = int(os.getenv("DEFAULT_WATERING_SECONDS", "3"))


@router.get("/sensor-data", response_class=HTMLResponse)
async def get_sensor_data(request: Request):
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
async def water_plant(request: Request, user=Depends(require_user_htmx)):
    """觸發 ESP32 執行澆水動作"""
    # 2. 發送指令給 ESP32
    await reader.send_command("water", {"seconds": WATERING_SECONDS})

    # 3. 無論成功與否，都回傳最新的感測器片段 (讓 UI 根據真實狀態更新)
    # 如果指令發送成功，ESP32 應該會很快回傳 watering: true，從而顯示彈窗
    return await get_sensor_data(request)
