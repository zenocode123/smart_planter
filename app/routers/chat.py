from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth import require_user_htmx
from app.models import Plant, ChatMessage
from openai import OpenAI
import os
import logging

router = APIRouter(prefix="/chat", tags=["chat"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

# Nvidia NIM 設定
NVIDIA_NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY")
NVIDIA_MODEL_NAME = os.getenv("NVIDIA_MODEL_NAME")
NVIDIA_NIM_BASE_URL = os.getenv("NVIDIA_NIM_BASE_URL")

def get_ai_client():
    if not NVIDIA_NIM_API_KEY or not NVIDIA_NIM_BASE_URL:
        return None
    return OpenAI(
      base_url=NVIDIA_NIM_BASE_URL,
      api_key=NVIDIA_NIM_API_KEY
    )

from app.ai.prompts import get_chat_system_prompt, with_retry_sync

@with_retry_sync(max_retries=3)
def _call_nvidia_nim_for_chat(messages_payload: list) -> str:
    """內部函式：受 Retry 保護的 AI 聊天呼叫"""
    client = get_ai_client()
    if not client:
        raise ValueError("NVIDIA_NIM_API_KEY 未設定")
        
    response = client.chat.completions.create(
        model=NVIDIA_MODEL_NAME,
        messages=messages_payload,
        temperature=0.7,
        max_tokens=256,
        top_p=0.7
    )
    return response.choices[0].message.content.strip()

@router.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request, user=Depends(require_user_htmx)):
    """顯示對話頁面並加載歷史紀錄 (依據特定植物)"""
    plant = await Plant.first()
    if plant:
        messages = await ChatMessage.filter(plant=plant).order_by("created_at")
    else:
        messages = []
        
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

    # 1. 直接儲存使用者訊息，並明確綁定到特定植物
    plant = await Plant.first()
    user_msg = await ChatMessage.create(plant=plant, role="user", content=message)

    # 2. 回傳使用者片段與 AI 思考中的「自動觸發」佔位符
    return templates.TemplateResponse("chat_fragment.html", {
        "request": request,
        "user_msg": user_msg,
        "is_placeholder": True,
        "plant": plant
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

    # 獲取最近一筆感測器資料，並與儀表板共用 120 秒斷線判定邏輯
    from app.models import PlantLog
    import time
    from app.logic.mqtt_service import mqtt_service
    
    sensor_data = None
    if plant:
        latest_log = await PlantLog.filter(plant=plant).order_by("-created_at").first()
        if latest_log and latest_log.soil_moisture is not None:
            # 只要 MQTT 超過 120 秒未更新，即視為斷線 (與儀表板 /sensors 判定一致)
            last_update = mqtt_service.latest_update_time.get(plant.id, 0)
            if last_update > 0 and (time.time() - last_update) < 120:
                sensor_data = {
                    "temp": latest_log.temperature,
                    "hum": latest_log.humidity,
                    "moisture": latest_log.soil_moisture,
                    "lux": latest_log.lux
                }

    system_prompt = get_chat_system_prompt(
        base_personality, 
        species=plant.species if plant and plant.species else "植物",
        sensor_data=sensor_data
    )

    # 準備對話 context（取這條訊息之前的舊歷史，並嚴格使用 plant=plant 篩選）
    history = await ChatMessage.filter(
        plant=plant,
        id__lt=user_msg.id
    ).order_by("-created_at").limit(9)
    history = sorted(history, key=lambda x: x.created_at)

    messages_payload = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages_payload.append({"role": h.role, "content": h.content})
    messages_payload.append({"role": "user", "content": user_msg.content})

    # 呼叫 Nvidia NIM (具備 Retry 裝飾器防呆)
    ai_content = "（植物似乎在發呆，沒有回應...）"
    try:
        ai_content = _call_nvidia_nim_for_chat(messages_payload) or ai_content
    except Exception as e:
        logger.error(f"Chat AI Error: {e}")
        ai_content = f"（哎呀，我好像有點不舒服... 錯誤：{str(e)[:80]}）"

    # 儲存 AI 回覆，並綁定到特定植物
    ai_msg = await ChatMessage.create(plant=plant, role="assistant", content=ai_content)

    # 發出實體寵物表情 (電子雞互動)
    from app.logic.mqtt_service import mqtt_service
    import json
    if plant and plant.mqtt_topic_id and mqtt_service.client:
        topic = f"planter/{plant.mqtt_topic_id}/cmd"
        try:
            mqtt_service.client.publish(topic, json.dumps({"emotion": "happy"}))
        except Exception as e:
            logger.warning(f"Failed to publish emotion to MQTT: {e}")

    # 回傳最終的 AI 對話片段，替換掉原本的思考中佔位符
    return templates.TemplateResponse("chat_fragment.html", {
        "request": request,
        "ai_msg": ai_msg,
        "is_placeholder": False,
        "plant": plant
    })
