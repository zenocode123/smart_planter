"""
AI 人格生成模組 - 透過 Ollama API 為植物生成個性化人格
根據植物品種自動產生 System Prompt，用於後續 AI 對話 (UC08)
"""
from openai import OpenAI
import os
import logging

logger = logging.getLogger(__name__)

# Nvidia NIM 設定項目 (OpenAI 兼容)
NVIDIA_NIM_API_KEY: str = os.getenv("NVIDIA_NIM_API_KEY")
NVIDIA_MODEL_NAME: str = os.getenv("NVIDIA_MODEL_NAME")
NVIDIA_NIM_BASE_URL: str = os.getenv("NVIDIA_NIM_BASE_URL")

# 延遲初始化客戶端，避免啟動時因缺失 API Key 崩潰
def get_ai_client():
    if not NVIDIA_NIM_API_KEY or not NVIDIA_NIM_BASE_URL:
        return None
    return OpenAI(
      base_url=NVIDIA_NIM_BASE_URL,
      api_key=NVIDIA_NIM_API_KEY
    )

from app.ai.prompts import PERSONALITY_PROMPT, with_retry_sync

@with_retry_sync(max_retries=3)
def _call_nvidia_nim_for_personality(prompt: str) -> str:
    """內部函式：受 Retry 保護的 API 呼叫"""
    client = get_ai_client()
    if not client:
        raise ValueError("NVIDIA_NIM_API_KEY 未設定")
        
    response = client.chat.completions.create(
        model=NVIDIA_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=300,
        top_p=0.7
    )
    return response.choices[0].message.content.strip()

async def generate_personality(species: str, nickname: str) -> str | None:
    """
    呼叫 Nvidia NIM API 生成植物人格 System Prompt。
    """
    if not NVIDIA_NIM_API_KEY:
        logger.warning("⚠️ NVIDIA_NIM_API_KEY 未設定，無法生成人格。")
        return None

    prompt: str = PERSONALITY_PROMPT.format(nickname=nickname, species=species)

    try:
        personality = _call_nvidia_nim_for_personality(prompt)

        if personality:
            logger.info(f"✅ AI 人格已透過 Nvidia NIM 生成：{nickname}（{species}）")
            return personality
        else:
            logger.warning(f"⚠️ AI 回傳空白人格：{nickname}（{species}）")
            return None

    except Exception as e:
        logger.error(f"❌ Nvidia NIM 人格生成失敗：{e}")
        return None
