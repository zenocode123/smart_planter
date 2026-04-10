from tortoise import fields, models
from datetime import date


class User(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True, index=True)
    hashed_password = fields.CharField(max_length=255)
    
    # Gmail 整合與加密存儲
    email = fields.CharField(max_length=255, unique=True, index=True, null=True, description="用於登入與寄信的 Gmail")
    gmail_app_password = fields.TextField(null=True, description="加密後的應用程式密碼")
    encryption_salt = fields.CharField(max_length=100, null=True, description="加密使用的隨機鹽值")

    class Meta:
        table = "users"

    def __str__(self) -> str:
        return f"User({self.username} <{self.email}>)"


class Plant(models.Model):
    """植物檔案模型 - 支持一個帳號管理多盆植物"""
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="plants", null=True)
    
    nickname = fields.CharField(max_length=50, description="植物暱稱")
    species = fields.CharField(max_length=100, description="植物品種")
    planting_date = fields.DateField(null=True, description="種植日期")
    photo_path = fields.CharField(max_length=255, null=True, description="照片檔案路徑")
    ai_personality = fields.TextField(null=True, description="AI 人格 System Prompt")
    
    # MQTT 辨識 ID
    mqtt_topic_id = fields.CharField(max_length=100, unique=True, index=True, null=True, description="MQTT 通訊 ID (如 planter_01)")
    
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "plants"

    def __str__(self) -> str:
        return f"Plant({self.nickname}, {self.mqtt_topic_id})"


class ChatMessage(models.Model):
    """對話紀錄模型 - 綁定特定植物"""
    id = fields.IntField(pk=True)
    plant = fields.ForeignKeyField("models.Plant", related_name="messages", null=True)
    
    role = fields.CharField(max_length=20, description="角色 (user/assistant)")
    content = fields.TextField(description="對話內容")
    created_at = fields.DatetimeField(auto_now_add=True, index=True, description="訊息建立時間")

    class Meta:
        table = "chat_messages"

    def __str__(self) -> str:
        return f"Chat({self.plant_id}): {self.role}: {self.content[:20]}..."


class PlantLog(models.Model):
    """[UC10] 定時排程紀錄模型 - 綁定特定植物"""
    id = fields.IntField(pk=True)
    plant = fields.ForeignKeyField("models.Plant", related_name="logs", null=True)
    
    temperature = fields.FloatField(null=True, description="溫度")
    humidity = fields.FloatField(null=True, description="濕度")
    soil_moisture = fields.FloatField(null=True, description="土壤濕度")
    lux = fields.FloatField(null=True, description="光照度")
    
    photo_path = fields.CharField(max_length=255, null=True, description="相片儲存路徑")
    photo_blob = fields.BinaryField(null=True, description="照片 JPEG 原始 bytes（存入 DB）")
    chart_blob = fields.BinaryField(null=True, description="趨勢圖 PNG 原始 bytes（存入 DB）")
    ai_analysis = fields.TextField(null=True, description="AI 分析結果")
    watering_suggested = fields.BooleanField(default=False, description="是否建議澆水")
    
    created_at = fields.DatetimeField(auto_now_add=True, index=True, description="紀錄時間")

    class Meta:
        table = "plant_logs"

    def __str__(self) -> str:
        return f"Log(Plant:{self.plant_id}, {self.created_at})"

class WateringLog(models.Model):
    """手動/系統實際澆水紀錄模型"""
    id = fields.IntField(pk=True)
    plant = fields.ForeignKeyField("models.Plant", related_name="waterings", null=True)
    
    source = fields.CharField(max_length=20, description="來源 (manual/system)")
    duration = fields.FloatField(description="澆水秒數")
    
    created_at = fields.DatetimeField(auto_now_add=True, index=True, description="澆水時間")

    class Meta:
        table = "watering_logs"

    def __str__(self) -> str:
        return f"Watering(Plant:{self.plant_id}, {self.source}, {self.duration}s)"
