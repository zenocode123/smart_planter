from pydantic import BaseModel, Field, validator
from datetime import date
from typing import Optional

class PlantBase(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=50, description="植物暱稱")
    species: str = Field(..., min_length=1, max_length=100, description="植物品種")
    planting_date: Optional[date] = None

class PlantCreate(PlantBase):
    pass

class PlantUpdate(BaseModel):
    nickname: Optional[str] = Field(None, min_length=1, max_length=50)
    species: Optional[str] = Field(None, min_length=1, max_length=100)
    planting_date: Optional[date] = None

class PlantRead(PlantBase):
    id: int
    photo_path: Optional[str] = None
    ai_personality: Optional[str] = None
    
    class Config:
        from_attributes = True
