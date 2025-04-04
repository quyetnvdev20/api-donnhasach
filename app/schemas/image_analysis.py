from pydantic import BaseModel, HttpUrl
from typing import Optional
from app.config import ClaimImageStatus
from datetime import datetime

class ImageAnalysisRequest(BaseModel):
    analysis_id: str
    image_url: str
    image_id: str
    device_token: str
    auto_analysis: bool = False

class ImageAnalysisResponse(BaseModel):
    analysis_id: str
    assessment_id: str
    status: ClaimImageStatus
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    json_data: Optional[dict] = None
    scan_image_url: Optional[str] = None


# Thêm các models mới
class CategoryResponse(BaseModel):
    id: int
    name: str
    code: Optional[str] = None

class StatusResponse(BaseModel):
    id: int
    name: str
    code: Optional[str] = None

class AudioAnalysisResponse(BaseModel):
    category: Optional[CategoryResponse] = {}
    status: Optional[StatusResponse] = {}