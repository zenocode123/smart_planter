from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.serial_reader import reader
import asyncio
import os
from tortoise.contrib.fastapi import register_tortoise
from app.routers import auth, plants
from app.auth import NotAuthenticatedHTMX, require_user_htmx
from fastapi import status, Depends
import urllib.parse


@asynccontextmanager
async def lifespan(app: FastAPI):
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

# 掛載 Routers
app.include_router(auth.router)
app.include_router(plants.router)

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
    return templates.TemplateResponse(
        "index.html", {
            "request": request, 
            "user": user, 
            "msg": msg,
            "interval": update_interval
        }
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
            headers={"HX-Redirect": "/auth/login"}
        )
    else:
        url = "/auth/login?msg=" + urllib.parse.quote("請先登入")
        return RedirectResponse(url=url, status_code=303)
