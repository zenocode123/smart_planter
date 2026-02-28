from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from app.serial_reader import reader
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動伺服器時：開啟背景讀取任務
    task = asyncio.create_task(reader.run())
    yield
    # 關閉伺服器時：安全停止
    reader.stop()
    await task

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主頁面"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/sensor-data", response_class=HTMLResponse)
async def get_sensor_data(request: Request):
    """供 HTMX 定期調用的片段"""
    latest_data = reader.get_data()
    return templates.TemplateResponse("sensor_fragment.html", {
        "request": request,
        "data": latest_data
    })
