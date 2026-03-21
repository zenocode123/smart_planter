import asyncio
import os
import httpx
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.models import Plant, PlantLog, User
from app.logic.camera import capture_plant_photo
from app.logic.dataviz import generate_history_plot
from app.logic.mailer import send_health_report_email
from app.logic.mqtt_service import mqtt_service
from app.logic.security import secret_manager
from openai import OpenAI
import os
import logging

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

from app.ai.prompts import SCHEDULER_ANALYSIS_PROMPT, with_retry_sync, robust_json_parse

@with_retry_sync(max_retries=3)
def _call_nvidia_nim_for_scheduler(prompt: str) -> str:
    """內部函式：受 Retry 保護的 API 呼叫"""
    client = get_ai_client()
    if not client:
        raise ValueError("NVIDIA_NIM_API_KEY 未設定")
    response = client.chat.completions.create(
        model=NVIDIA_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=150
    )
    return response.choices[0].message.content.strip()

scheduler = AsyncIOScheduler()

async def analyze_plant_health(sensor_data: dict, plant_nickname: str, plant_species: str) -> dict:
    """呼叫 Nvidia NIM 分析健康狀況並決定是否需要澆水"""
    if not NVIDIA_NIM_API_KEY:
        return {"message": "AI Key 未設定，請檢查 .env。", "water_seconds": 0.0}

    prompt = SCHEDULER_ANALYSIS_PROMPT.format(
        plant_nickname=plant_nickname,
        plant_species=plant_species,
        temp=sensor_data.get('temp'),
        humidity=sensor_data.get('humidity'),
        moisture=sensor_data.get('moisture'),
        lux=sensor_data.get('lux')
    )
    
    try:
        text = _call_nvidia_nim_for_scheduler(prompt)
        parsed = robust_json_parse(text)
        
        return {
            "message": parsed.get("message", "AI 解析成功，但不含 message"),
            "water_seconds": float(parsed.get("water_seconds", 0.0))
        }
    except Exception as e:
        logger.error(f"❌ [Scheduler] AI 分析與 JSON 解析失敗: {e}")
        return {"message": "AI 模型目前無法分析，請看數據研判。", "water_seconds": 0.0}


async def daily_plant_routine():
    """定時執行偵測、拍照、分析、存檔、畫圖與寄信的排程任務 (支持多植物)"""
    logger.info(f"⏰ [Scheduler] 執行全系統植物健康檢查 ({datetime.now().strftime('%H:%M:%S')})")
    
    plants = await Plant.all().prefetch_related("user")
    if not plants:
        logger.warning("⚠️ [Scheduler] 系統內尚未設定植物檔案，跳過排程任務。")
        return
        
    for plant in plants:
        logger.info(f"🌿 [Scheduler] 正在檢查植物：{plant.nickname} ({plant.mqtt_topic_id})")
        
        # 1. 取得最新環境感測數據 (從資料庫獲取最新一筆 MQTT 存入的 Log)
        latest_log = await PlantLog.filter(plant=plant).order_by("-created_at").first()
        if not latest_log:
            logger.warning(f"⚠️ [Scheduler] 植物 {plant.nickname} 尚無感測數據。")
            sensor_data = {}
        else:
            sensor_data = {
                "temp": latest_log.temperature,
                "humidity": latest_log.humidity,
                "moisture": latest_log.soil_moisture,
                "lux": latest_log.lux
            }
        
        # 2. 相機拍照 (目前支援單一相機，未來可擴展)
        loop = asyncio.get_event_loop()
        photo_path = await loop.run_in_executor(None, capture_plant_photo)
        
        # 3. 呼叫 AI 進行分析
        analysis = await analyze_plant_health(sensor_data, plant.nickname, plant.species)
        ai_message = analysis["message"]
        needs_water = analysis.get("water_seconds", 0) > 0
        
        # 4. 更新日誌中的 AI 分析與照片 (或是建立新日誌)
        # 這裡我們選擇更新最新一筆，或者建立新的一筆作為報表紀錄
        report_log = await PlantLog.create(
            plant=plant,
            temperature=sensor_data.get('temp'),
            humidity=sensor_data.get('humidity'),
            soil_moisture=sensor_data.get('moisture'),
            lux=sensor_data.get('lux'),
            photo_path=photo_path,
            ai_analysis=ai_message,
            watering_suggested=needs_water
        )
        
        # 5. 繪製並更新圖表 (針對特定植物)
        # 這裡需要傳入 plant_id
        plot_path = await generate_history_plot(limit=50, plant_id=plant.id)
        
        # 6. 寄送 Email (獲取使用者的解密憑證)
        if plant.user and plant.user.gmail_app_password:
            decrypted_pwd = secret_manager.decrypt(plant.user.gmail_app_password)
            await send_health_report_email(
                sensor_data, 
                ai_message, 
                photo_path,
                smtp_user=plant.user.email,
                smtp_password=decrypted_pwd
            )
        else:
            logger.warning("⚠️ [Scheduler] 該植物未綁定使用者，或使用者未提供 Gmail 應用密碼，不寄送信件。")
        
        # 7. 若需要澆水，發送 MQTT 澆水與情緒指令
        if plant.mqtt_topic_id and mqtt_service.client:
            water_seconds = analysis.get("water_seconds", 0.0)
            topic = f"planter/{plant.mqtt_topic_id}/cmd"
            
            if water_seconds > 0:
                logger.info(f"💧 [Scheduler] AI 建議澆水！正在發送 MQTT 指令... 澆水 {water_seconds} 秒")
                cmd_payload = {"action": "water", "duration": water_seconds}
                mqtt_service.client.publish(topic, json.dumps(cmd_payload))
            else:
                # 不澆水代表狀況不錯，或者是太濕，發送情緒回饋
                emotion = "happy" if sensor_data.get("moisture", 0) > 30 else "sleepy"
                logger.info(f"😁 [Scheduler] 發送情緒對話 {emotion}...")
                mqtt_service.client.publish(topic, json.dumps({"emotion": emotion}))
    
    logger.info("✅ [Scheduler] 全系統植物健康檢查完成！")

def init_scheduler():
    """啟動排程器。在此為了測試我們設定每 2 分鐘執行一次。"""
    scheduler.add_job(daily_plant_routine, IntervalTrigger(minutes=2), id='daily_plant_routine', replace_existing=True)
    scheduler.start()
    print("🚀 [Scheduler] 排程器已啟動 (每2分鐘執行一次)")
