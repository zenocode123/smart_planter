"""
AI 人格生成模組 - 透過 Ollama API 為植物生成個性化人格
根據植物品種自動產生 System Prompt，用於後續 AI 對話 (UC08)
"""
import httpx
import os
import logging

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2:0.5b")

# 人格生成的 Meta Prompt（優化版：結構清晰，強制繁中輸出）
PERSONALITY_META_PROMPT: str = """You are a plant personality designer. Create a personality for this plant in Traditional Chinese (繁體中文).

Plant nickname: {nickname}
Plant species: {species}

Write a first-person self-introduction for this plant in Traditional Chinese. The text should be 80-120 characters long and include:
1. One key characteristic of this plant species (e.g., drought-tolerant, loves sunlight, needs moist soil)
2. A humanized personality derived from that characteristic
3. A unique speaking style or catchphrase

IMPORTANT RULES:
- Write ONLY the personality description, nothing else
- Use Traditional Chinese (繁體中文) only
- Write in first person ("我")
- Do NOT use simplified Chinese
- Do NOT include English
- Keep it under 150 characters

Example output style:
「嗨！我是多多，一株驕傲的多肉植物。我天生耐旱，在沙漠中都能活下來，所以我特別有韌性。偶爾澆點水就夠了，別把我寵壞～」"""


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
                    "keep_alive": "30m",
                    "options": {
                        "temperature": 0.8,
                        "num_predict": 300,
                        "num_ctx": 1024,
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
