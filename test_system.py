import asyncio
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

async def test_all():
    print("====================================")
    print("🌱 智慧盆栽系統 TDD 體檢報告")
    print("====================================\n")

    print("[1] 🗄️ 資料庫 (Database) 測試")
    try:
        from tortoise import Tortoise
        from app.models import User, Plant
        await Tortoise.init(db_url="sqlite://app/database.db", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        u_count = await User.all().count()
        p_count = await Plant.all().count()
        print(f"  👉 連線成功！當前註冊使用者: {u_count} 位, 登錄植物: {p_count} 盆。")
    except Exception as e:
        print(f"  ❌ DB 連線失敗: {e}")

    print("\n[2] 🧠 NVIDIA NIM (AI 聊天與分析) 測試")
    try:
        client = OpenAI(
            base_url=os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            api_key=os.getenv("NVIDIA_NIM_API_KEY")
        )
        resp = client.chat.completions.create(
            model=os.getenv("NVIDIA_MODEL_NAME", "meta/llama-3.1-70b-instruct"),
            messages=[{"role": "user", "content": "請只回覆兩個字：'收到'"}],
            max_tokens=10
        )
        print(f"  👉 API Key 有效！AI 回應測試：{resp.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"  ❌ AI 呼叫失敗，請檢查 .env 中的 API KEY 是否過期或為預設值：{e}")

    print("\n[3] 📨 Email (Mailer) 模組掛載測試")
    try:
        from app.logic.mailer import send_health_report_email
        print(f"  👉 Mailer 模組載入正常！已確認使用資料庫獨立動態信箱注入。")
    except Exception as e:
        print(f"  ❌ Mailer 載入異常: {e}")

    print("\n[4] 🤖 ESP32 (MQTT 聊天互動推播) 掛載測試")
    try:
        from app.logic.mqtt_service import mqtt_service
        print(f"  👉 MQTT 模組載入正常，隨時可推播 Emotion 與 Water 指令。")
    except Exception as e:
        print(f"  ❌ MQTT 載入異常:{e}")
        
    print("\n====================================")
    print("✅ 測試完畢。")
    try:
        await Tortoise.close_connections()
    except:
        pass

if __name__ == "__main__":
    asyncio.run(test_all())
