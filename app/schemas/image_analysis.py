from pydantic import BaseModel, HttpUrl
from typing import Optional
from app.config import ClaimImageStatus
from datetime import datetime

class ImageAnalysisRequest(BaseModel):
    folder_id: str
    image_id: str
    image_url: str
    device_token: str

class ImageAnalysisResponse(BaseModel):
    image_id: str
    status: ClaimImageStatus
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    json_data: Optional[dict] = None
    scan_image_url: Optional[str] = None