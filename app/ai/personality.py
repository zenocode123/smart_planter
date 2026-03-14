"""
AI 人格生成模組 - 透過 Ollama API 為植物生成個性化人格
根據植物品種自動產生 System Prompt，用於後續 AI 對話 (UC08)
"""
import httpx
import os
import logging

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "phi3:mini")

# 人格生成的 Meta Prompt（請 AI 生成 System Prompt）
PERSONALITY_META_PROMPT: str = """你是一位植物人格設計師。請根據以下植物資訊，設計一段「植物人格描述」。

植物暱稱：{nickname}
植物品種：{species}

請用第一人稱撰寫這個植物的自我介紹與性格描述（約 100-150 字），包含：
1. 該品種的真實特性（耐旱/喜水/喜光等）
2. 由特性延伸的擬人化性格（例如：仙人掌 → 堅強獨立；黃金葛 → 隨和好養）
3. 說話風格與語氣特色

請直接輸出人格描述，不要有任何額外說明或標題。用繁體中文回答。"""


async def generate_personality(species: str, nickname: str) -> str | None:
    """
    呼叫 Ollama API 生成植物人格 System Prompt。

    Args:
        species: 植物品種
        nickname: 植物暱稱

    Returns:
        生成的人格描述文字，或 None（若生成失敗）
    """
    prompt: str = PERSONALITY_META_PROMPT.format(nickname=nickname, species=species)

    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,
                        "num_predict": 300,
                    },
                },
            )
            resp.raise_for_status()
            result: dict = resp.json()
            personality: str = result.get("response", "").strip()

            if personality:
                logger.info(f"✅ AI 人格已生成：{nickname}（{species}）")
                return personality
            else:
                logger.warning(f"⚠️ AI 回傳空白人格：{nickname}（{species}）")
                return None

    except httpx.TimeoutException:
        logger.error(f"❌ Ollama 請求超時（600s）：{nickname}（{species}）")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Ollama HTTP 錯誤 {e.response.status_code}：{e}")
        return None
    except Exception as e:
        logger.error(f"❌ AI 人格生成失敗：{e}")
        return None
