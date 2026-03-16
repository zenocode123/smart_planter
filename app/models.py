from tortoise import fields, models
from datetime import date


class User(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True, index=True)
    hashed_password = fields.CharField(max_length=255)

    class Meta:
        table = "users"

    def __str__(self) -> str:
        return f"User({self.username})"


class Plant(models.Model):
    """植物檔案模型 - 每台裝置只管理一株植物"""
    id = fields.IntField(pk=True)
    nickname = fields.CharField(max_length=50, description="植物暱稱（必填）")
    species = fields.CharField(max_length=100, description="植物品種（必填）")
    planting_date = fields.DateField(null=True, description="種植日期")
    photo_path = fields.CharField(max_length=255, null=True, description="照片檔案路徑")
    ai_personality = fields.TextField(null=True, description="AI 人格 System Prompt（由品種自動生成）")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "plants"

    def __str__(self) -> str:
        return f"Plant({self.nickname}, {self.species})"


class ChatMessage(models.Model):
    """對話紀錄模型"""
    id = fields.IntField(pk=True)
    role = fields.CharField(max_length=20, description="角角色 (user/assistant)")
    content = fields.TextField(description="對話內容")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_messages"

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:20]}..."
