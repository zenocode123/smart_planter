from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from app.auth import require_user_htmx
from app.models import Plant

router = APIRouter(prefix="/system", tags=["system"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/settings", response_class=HTMLResponse)
async def get_system_settings(request: Request, user=Depends(require_user_htmx)):
    """顯示系統設定頁面"""
    plant = await Plant.first()
    return templates.TemplateResponse(
        "system_settings.html",
        {
            "request": request,
            "user": user,
            "plant": plant,
        },
    )

@router.post("/settings", response_class=HTMLResponse)
async def post_system_settings(
    request: Request,
    user=Depends(require_user_htmx),
    auto_water: bool = Form(False)
):
    """儲存系統設定 (例如自動澆水)"""
    plant = await Plant.first()
    if plant:
        plant.auto_water = auto_water
        await plant.save()
        
    return HTMLResponse(
        content='''
        <div class="toast-notice-container" x-data="{ show: true }" x-show="show" x-init="setTimeout(() => show = false, 3000)" x-transition>
            <article class="toast-notice-card solid-popup-bg">
                <span class="toast-notice-text">✅ 系統設定已儲存</span>
            </article>
        </div>
        '''
    )
