from tortoise import fields, models


class User(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True, index=True)
    hashed_password = fields.CharField(max_length=255)

    class Meta:
        table = "users"

    def __str__(self):
        return f"User({self.username})"
