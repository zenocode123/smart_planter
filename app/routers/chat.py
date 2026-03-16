from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth import require_user_htmx
from app.models import Plant, ChatMessage
import httpx
import os
import logging

router = APIRouter(prefix="/chat", tags=["chat"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2:0.5b")

@router.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request, user=Depends(require_user_htmx)):
    """顯示對話頁面並加載歷史紀錄"""
    messages = await ChatMessage.all().order_by("created_at")
    plant = await Plant.first()
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "user": user,
        "messages": messages,
        "plant": plant
    })

@router.post("/", response_class=HTMLResponse)
async def post_chat_message(
    request: Request,
    user=Depends(require_user_htmx),
    message: str = Form(...)
):
    """處理使用者訊息，快速回傳並觸發 AI 非同步生成"""
    message = message.strip()
    if not message:
        return HTMLResponse(content="")

    # 1. 直接儲存使用者訊息
    user_msg = await ChatMessage.create(role="user", content=message)

    # 2. 回傳使用者片段與 AI 思考中的「自動觸發」佔位符
    return templates.TemplateResponse("chat_fragment.html", {
        "request": request,
        "user_msg": user_msg,
        "is_placeholder": True
    })

@router.post("/generate/{user_msg_id}", response_class=HTMLResponse)
async def generate_chat_response(
    user_msg_id: int,
    request: Request,
    user=Depends(require_user_htmx)
):
    """真正呼叫 Ollama 生成 AI 回覆的路由"""
    user_msg = await ChatMessage.get_or_none(id=user_msg_id)
    if not user_msg:
        return HTMLResponse(content="")

    # 獲取植物人格
    plant = await Plant.first()
    if plant and plant.ai_personality:
        base_personality = plant.ai_personality
    else:
        nickname = plant.nickname if plant and plant.nickname else "小植"
        base_personality = f"你是一株名為「{nickname}」的可愛植物。你的個性活潑友善。"

    system_prompt = f"{base_personality}\n\n請務必遵守以下規則：\n1. 用第一人稱「我」來對話，並且只使用繁體中文（Traditional Chinese）。\n2. 你的回應應該簡短、口語化，不要給出長篇大論或點列式回答。\n3. 不要自稱是 AI、Assistant 或助手，你就是一株真實存在的植物。"

    # 準備對話 context（取這條訊息之前的舊歷史）
    history = await ChatMessage.filter(
        id__lt=user_msg.id
    ).order_by("-created_at").limit(9)
    history = sorted(history, key=lambda x: x.created_at)

    messages_payload = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages_payload.append({"role": h.role, "content": h.content})
    messages_payload.append({"role": "user", "content": user_msg.content})

    # 呼叫 Ollama
    ai_content = "（植物似乎在發呆，沒有回應...）"
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages_payload,
                    "stream": False,
                    "keep_alive": "30m",
                    "options": {
                        "num_ctx": 1024,
                        "num_predict": 100
                    }
                }
            )
            resp.raise_for_status()
            ai_resp = resp.json()
            ai_content = ai_resp.get("message", {}).get("content", "").strip() or ai_content
    except Exception as e:
        logger.error(f"Chat AI Error: {e}")
        ai_content = f"（哎呀，我好像有點不舒服... 錯誤：{str(e)[:80]}）"

    # 儲存 AI 回覆
    ai_msg = await ChatMessage.create(role="assistant", content=ai_content)

    # 回傳最終的 AI 對話片段，替換掉原本的思考中佔位符
    return templates.TemplateResponse("chat_fragment.html", {
        "request": request,
        "ai_msg": ai_msg,
        "is_placeholder": False
    })
