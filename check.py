import asyncio
from tortoise import Tortoise
from app.models import WateringLog, PlantLog

async def test():
    await Tortoise.init(db_url='sqlite://app/database.db', modules={'models': ['app.models']})
    await Tortoise.generate_schemas()
    c = await WateringLog.all().count()
    print("WateringLog count:", c)

asyncio.run(test())
