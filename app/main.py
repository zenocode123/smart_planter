from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
import os
from tortoise.contrib.fastapi import register_tortoise
from app.scheduler import init_scheduler
from app.logic.mqtt_service import mqtt_service
from app.routers import auth, plants, chat
from app.auth import NotAuthenticatedHTMX, require_user_htmx
from app.models import Plant
from fastapi import status, Depends
import urllib.parse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize and start scheduler

    # Initialize and start scheduler
    init_scheduler()

    # 啟動 MQTT 監聽服務
    asyncio.create_task(mqtt_service.run())

    yield

    # 停止 MQTT 服務
    mqtt_service.stop()
    print("Cleanup complete.")


# 系統底層最佳化：強制為本機 SQLite 開啟 WAL 與同步模式 (對抗 database is locked 問題)
import sqlite3
import os

db_path = "app/database.db"
# 若資料夾不存在則創建 (預防首次啟動)
os.makedirs("app", exist_ok=True)
try:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.close()
except Exception as e:
    print(f"Warning: Failed to set SQLite PRAGMA - {e}")

app = FastAPI(lifespan=lifespan)

# 掛載靜態檔案資料夾
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# ── 路由註冊 ──

app.include_router(auth.router)
app.include_router(plants.router)  # /plants
app.include_router(chat.router)

# 註冊 Tortoise ORM
register_tortoise(
    app,
    db_url="sqlite://app/database.db",
    modules={"models": ["app.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user=Depends(require_user_htmx), msg: str = None):
    # 此處不再需要使用 try...except 捕捉 HTTPException。
    # 如果使用者未登入，require_user_htmx 預期會拋出 NotAuthenticatedHTMX。
    update_interval = int(os.getenv("SYSTEM_UPDATE_INTERVAL", "5"))
    plant = await Plant.first()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "msg": msg,
            "interval": update_interval,
            "plant": plant,
        },
    )


@app.exception_handler(NotAuthenticatedHTMX)
async def htmx_auth_exception_handler(request: Request, exc: NotAuthenticatedHTMX):
    # 對於根目錄 ("/") 的直接訪問 (非 HTMX 的 AJAX 請求)，如果未登入，
    # 需要重導向回 /login 頁面，而不是只回傳一段字串 (會導致瀏覽器只顯示「請先登入」黑字在白底)。
    # 判斷是否為 HTMX 請求可以透過檢查 HTTP Header 'HX-Request'
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content="請先登入",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"HX-Redirect": "/auth/login"},
        )
    else:
        url = "/auth/login?msg=" + urllib.parse.quote("請先登入")
        return RedirectResponse(url=url, status_code=303)
