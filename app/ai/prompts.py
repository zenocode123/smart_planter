import json
import logging
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)

class PromptTemplate:
    """Prompt 集中管理模版引擎 (實作自 llm-app-patterns)"""
    def __init__(self, template: str, variables: list[str]):
        self.template = template
        self.variables = variables

    def format(self, **kwargs) -> str:
        missing = set(self.variables) - set(kwargs.keys())
        if missing:
            raise ValueError(f"Missing variables in prompt: {missing}")
        return self.template.format(**kwargs)


# ==========================================
# 1. 植物人格產生器 (Personality Settings)
# ==========================================
PERSONALITY_PROMPT = PromptTemplate(
    template="""You are a plant personality designer. Create a personality for this plant in Traditional Chinese (繁體中文).

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
- Keep it under 150 characters""",
    variables=["nickname", "species"]
)


# ==========================================
# 2. 定時排程 AI 健康分析 (Scheduler Analysis)
# ==========================================
SCHEDULER_ANALYSIS_PROMPT = PromptTemplate(
    template="""請以繁體中文分析這株名為 {plant_nickname} ({plant_species}) 的現況：
溫度：{temp} °C
濕度：{humidity} %
土壤濕度：{moisture} %
光照：{lux} Lux

請在 50 字內寫一段給主人的狀態小語。
並且必須以嚴格的 JSON 格式回傳，不可有任何 JSON 以外的文字。
JSON 格式範例：
{{
  "message": "主人的狀態小語",
  "water_seconds": 1.5 
}}
說明：water_seconds 代表建議幫他澆水幾秒。如果不需要澆水（例如土壤很濕或現狀良好），請務必輸出 0.0。最多不超過 3.0 秒。""",
    variables=["plant_nickname", "plant_species", "temp", "humidity", "moisture", "lux"]
)


# ==========================================
# 3. 聊天室系統指令 (Chatbot System Prompt)
# ==========================================
def get_chat_system_prompt(base_personality: str) -> str:
    return f"{base_personality}\n\n請務必遵守以下規則：\n1. 用第一人稱「我」來對話，並且只使用繁體中文（Traditional Chinese）。\n2. 你的回應應該簡短、口語化，不要給出長篇大論或點列式回答。\n3. 不要自稱是 AI、Assistant 或助手，你就是一株真實存在的植物。"


# ==========================================
# 共用工具：重試機制 (Rate Limit Protection) 
# ==========================================
def with_retry_sync(max_retries=3, delay_seconds=2):
    """應用於呼叫 OpenAI 同步 API 的裝飾器，提供自動指數退避重試"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"⚠️ AI API 呼叫失敗 (嘗試 {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        time.sleep(delay_seconds * attempt)
            logger.error(f"❌ AI 呼叫經過 {max_retries} 次重試後仍然失敗。")
            raise last_exception
        return wrapper
    return decorator


# ==========================================
# 共用工具：JSON 結構化解析防呆
# ==========================================
def robust_json_parse(json_str: str) -> dict:
    """安全的 JSON 解析器，處理 AI 可能包在 markdown block (```json) 中的邊角情況"""
    json_str = json_str.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    elif json_str.startswith("```"):
        json_str = json_str[3:]
    
    if json_str.endswith("```"):
        json_str = json_str[:-3]
        
    return json.loads(json_str.strip())
