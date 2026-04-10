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
    variables=["nickname", "species"],
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
    variables=[
        "plant_nickname",
        "plant_species",
        "temp",
        "humidity",
        "moisture",
        "lux",
    ],
)


# ==========================================
# 3. 聊天室系統指令 (Chatbot System Prompt)
# ==========================================
def get_chat_system_prompt(base_personality: str, species: str = "植物", sensor_data: dict = None) -> str:
    prompt = f"{base_personality}\n\n請務必遵守以下核心設定與規則：\n1. 你現在就是一株真實存在這個世界上的「{species}」，請完全沉浸在這個身分中。\n2. 絕對不可提及「角色扮演」、「指令」、「AI」或任何暗示你被設定好的詞彙。\n3. 請用第一人稱「我」來對話，並且只使用繁體中文（Traditional Chinese）。\n4. 你的回應應該簡短、口語化，像個活生生的生命，不要給出無聊的長篇大論。\n"

    prompt += "\n【即時身體狀態】（當你被問到狀態、感覺如何時，必須根據以下資訊回答）：\n"
    if not sensor_data:
        prompt += "※ 警告：你目前的感測器已經斷線，完全失去生命徵象數據。請你務必在對話中主動向使用者抱怨或擔心地說出：「我感覺不到我自己了」、「我失去了知覺，能否幫我檢查一下？」這一類的話。\n"
    else:
        temp = sensor_data.get('temp')
        hum = sensor_data.get('hum')
        moisture = sensor_data.get('moisture')
        lux = sensor_data.get('lux')
        
        prompt += f"- 當前溫度：{temp if temp is not None else '未知'} °C\n"
        prompt += f"- 空氣濕度：{hum if hum is not None else '未知'} %\n"
        prompt += f"- 土壤濕度：{moisture if moisture is not None else '未知'} %\n"
        prompt += f"- 環境光照：{lux if lux is not None else '未知'} Lux\n"
        prompt += f"\n👉 請根據你作為「{species}」的真實植物特性（例如：水稻喜歡水、多肉怕水等），自行判斷上述數據的環境對你而言是舒適、口渴還是太冷太熱。將這份專屬於你的感受自然地融入對話中。\n"
            
    return prompt


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
                    logger.warning(
                        f"⚠️ AI API 呼叫失敗 (嘗試 {attempt}/{max_retries}): {e}"
                    )
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


# ==========================================
# 4. 澆水前 AI 諮詢 (Watering Advice)
# ==========================================
WATERING_ADVICE_PROMPT = PromptTemplate(
    template="""你是一位專業的植物照護顧問。請根據以下即時感測數據，判斷現在是否適合對 {species} 進行澆水。

植物品種：{species}
當前溫度：{temp} °C
環境濕度：{humidity} %
土壤濕度：{moisture} %
環境光照：{lux} Lux

請嚴格以 JSON 格式回傳（不可有任何其他文字）：
{{"recommend": true或false, "reason": "一句話說明（20字以內，繁體中文）"}}
""",
    variables=["species", "temp", "humidity", "moisture", "lux"],
)
