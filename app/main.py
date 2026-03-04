from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.serial_reader import reader
import asyncio
from datetime import datetime
from tortoise.contrib.fastapi import register_tortoise
from tortoise import Tortoise

from app.routers import auth
from app.auth import get_current_user
from fastapi import Depends, HTTPException, status
import urllib.parse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化資料庫 (用 RegisterTortoise 後這段移除，改到下面)

    # 啟動伺服器時：開啟背景讀取任務
    task = asyncio.create_task(reader.run())
    yield
    # 關閉伺服器時：安全停止
    reader.stop()
    await task


app = FastAPI(lifespan=lifespan)

# 掛載靜態檔案資料夾
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# 掛載 Auth Route
app.include_router(auth.router)

# 註冊 Tortoise ORM
register_tortoise(
    app,
    db_url="sqlite://app/database.db",  # 建議加上資料夾路徑確保路徑正確
    modules={"models": ["app.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, msg: str = None):
    try:
        user = await get_current_user(request)
        return templates.TemplateResponse(
            "index.html", {"request": request, "user": user, "msg": msg}
        )
    except HTTPException as e:
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            # 改成跳轉 (Redirect) 到 /login 路由 ✅ 
            url = "/login?msg=" + urllib.parse.quote("請先登入")
            return RedirectResponse(url=url, status_code=303)
        raise e

@app.get("/sensor-data", response_class=HTMLResponse)
async def get_sensor_data(request: Request):
    """供 HTMX 定期調用的片段"""
    latest_data = reader.get_data()
    # 獲取目前時間，用於前端驗證數據更新
    now = datetime.now().strftime("%H:%M:%S")
    return templates.TemplateResponse(
        "sensor_fragment.html",
        {"request": request, "data": latest_data, "update_time": now},
    )
