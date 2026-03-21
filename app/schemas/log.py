from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class PlantLogBase(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    lux: Optional[float] = None
    watering_suggested: bool = False

class PlantLogRead(PlantLogBase):
    id: int
    photo_path: Optional[str] = None
    ai_analysis: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
