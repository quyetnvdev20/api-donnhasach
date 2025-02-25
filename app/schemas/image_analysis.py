from pydantic import BaseModel, HttpUrl
from typing import Optional
from app.config import ImageStatus
from datetime import datetime

class ImageAnalysisRequest(BaseModel):
    session_id: str
    image_id: str
    image_url: HttpUrl

class ImageAnalysisResponse(BaseModel):
    image_id: str
    status: ImageStatus
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    json_data: Optional[dict] = None
    scan_image_url: Optional[HttpUrl] = None