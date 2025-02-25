from pydantic import BaseModel, HttpUrl
from typing import Optional
from app.config import ClaimImageStatus
from datetime import datetime

class ImageAnalysisRequest(BaseModel):
    analysis_id: str
    image_url: str
    device_token: str

class ImageAnalysisResponse(BaseModel):
    analysis_id: str
    assessment_id: str
    status: ClaimImageStatus
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    json_data: Optional[dict] = None
    scan_image_url: Optional[str] = None