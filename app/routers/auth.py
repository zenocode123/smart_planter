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

router = APIRouter()
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
    user = await User.get_or_none(username=username)
    if not user or not verify_password(password, user.hashed_password):
        # 帳號或密碼錯誤：回傳一段紅色的 HTML 錯誤訊息給 HTMX 掛載到表單裡
        return HTMLResponse(
            content='<span style="color:var(--pico-del-color);">❌ 帳號或密碼錯誤</span>'
        )

    # 成功登入
    access_token_expires = timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
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
):
    # 檢查是否已存在該帳號
    user = await User.get_or_none(username=username)
    if user:
        return HTMLResponse(
            content='<span style="color:var(--pico-del-color);">❌ 此帳號已經有人使用</span>'
        )

    # 新增 User
    hashed_pw = get_password_hash(password)
    new_user = await User.create(username=username, hashed_password=hashed_pw)

    resp = HTMLResponse(content="註冊成功，請登入...")

    # 在完成註冊後，引導使用者前往登入頁，帶上 flash message
    import urllib.parse

    redirect_url = "/login?msg=" + urllib.parse.quote("註冊成功！請登入你的新帳號")
    resp.headers["HX-Redirect"] = redirect_url

    return resp


@router.post("/logout", response_class=HTMLResponse)
async def post_logout():
    """
    接收 HTMX 的登出請求，清除 Cookie 並跳回首頁（首頁若沒 Cookie 則會重導向至 login）
    """
    resp = HTMLResponse(content="")
    resp.delete_cookie(key="access_token")
    resp.headers["HX-Redirect"] = "/login"
    return resp
