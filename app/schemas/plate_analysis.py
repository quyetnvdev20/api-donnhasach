from pydantic import BaseModel, HttpUrl
from typing import Optional

class PlateDetailResponse(BaseModel):
    plate_number: str
    analyzing_count: int
    manual_tagging_count: int
    category_count: int
    vehicle_image_url: str

class ImageUploadRequest(BaseModel):
    image_url: str
    description: Optional[str] = None 