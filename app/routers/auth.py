from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.models import User
from app.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_SECONDS,
)
from datetime import timedelta
from app.logic.security import secret_manager

router = APIRouter(prefix="/auth")
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request, msg: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "msg": msg})


@router.post("/login", response_class=HTMLResponse)
async def post_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: bool = Form(False),
):
    user = await User.get_or_none(email=username)  # 前端傳來的 username 欄位現在填的是 email
    if not user or not verify_password(password, user.hashed_password):
        # 帳號或密碼錯誤
        return HTMLResponse(
            content='<span style="color:var(--pico-del-color);">❌ Email 或密碼錯誤</span>'
        )

    # 成功登入
    access_token_expires = timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    resp = HTMLResponse(content="登入成功，正在導向...")

    # 設定 HTMX 的 Header 以要求前端導向到首頁 / 帶上 flash message
    import urllib.parse

    redirect_url = "/?msg=" + urllib.parse.quote("登入成功！歡迎回來")
    resp.headers["HX-Redirect"] = redirect_url

    # 根據是否勾選「記住我」來決定 Cookie 是否為 Session Cookie (關閉瀏覽器失效)
    cookie_max_age = ACCESS_TOKEN_EXPIRE_SECONDS if remember_me else None

    # 設定 HTTP-Only Cookie
    resp.set_cookie(
        key="access_token",
        value=f"{access_token}",
        httponly=True,
        max_age=cookie_max_age,
        samesite="lax",
        secure=False,  # 若是 https 應設為 True
    )

    return resp


@router.get("/register", response_class=HTMLResponse)
async def get_register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_class=HTMLResponse)
async def post_register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    gmail_app_password: str = Form(...),
):
    # 檢查是否已存在該 Email
    user = await User.get_or_none(email=email)
    if user:
        return HTMLResponse(
            content='<span style="color:var(--pico-del-color);">❌ 此 Email 已經註冊過</span>'
        )

    # 加密 Gmail 應用程式密碼
    encrypted_gmail_pw = secret_manager.encrypt(gmail_app_password)

    # 新增 User
    hashed_pw = get_password_hash(password)
    new_user = await User.create(
        username=username, 
        email=email,
        hashed_password=hashed_pw,
        gmail_app_password=encrypted_gmail_pw
    )

    # 動態配發預設植物 (預設使用 planter_01)
    from app.models import Plant
    import uuid
    existing_plant = await Plant.get_or_none(mqtt_topic_id="planter_01")
    topic_id = "planter_01" if not existing_plant else f"planter_{uuid.uuid4().hex[:4]}"
    await Plant.create(
        user=new_user,
        nickname="我的第一盆植物",
        species="溫室植物",
        mqtt_topic_id=topic_id
    )

    resp = HTMLResponse(content="註冊成功，請登入...")

    # 在完成註冊後，引導使用者前往登入頁，帶上 flash message
    import urllib.parse

    redirect_url = "/auth/login?msg=" + urllib.parse.quote("註冊成功！請登入你的新帳號")
    resp.headers["HX-Redirect"] = redirect_url

    return resp


@router.post("/logout", response_class=HTMLResponse)
async def post_logout():
    """
    接收 HTMX 的登出請求，清除 Cookie 並跳回首頁（首頁若沒 Cookie 則會重導向至 login）
    """
    resp = HTMLResponse(content="")
    resp.delete_cookie(key="access_token")
    resp.headers["HX-Redirect"] = "/auth/login"
    return resp
