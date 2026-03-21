import os
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import JWTError, jwt
from fastapi import Request, HTTPException, status
from dotenv import load_dotenv
from app.models import User

load_dotenv()

# JWT 設定參數
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", 604800))


def verify_password(plain_password, hashed_password):
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_password_hash(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(seconds=15 * 60)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(request: Request):
    """
    從 HttpOnly Cookie 讀取 token
    """
    # 這裡我們預期 Cookie 名字為 'access_token'
    token = request.cookies.get("access_token")
    if not token:
        # FastAPI 中若需要重導向前端，我們在 HTMX 環境常透過 response header 回傳。
        # 不過 Dependency 裡面直接丟 HTTP 401 ，可以讓首頁路由決定怎麼處理。
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # 處理如果 token 前有 'Bearer ' 的情況 (若是純字串則不影響)
    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    # 用 Email 查資料庫
    user = await User.get_or_none(email=email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    return user

class NotAuthenticatedHTMX(Exception):
    pass

async def require_user_htmx(request: Request):
    try:
        return await get_current_user(request)
    except HTTPException:
        raise NotAuthenticatedHTMX()
