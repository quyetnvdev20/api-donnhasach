from pydantic import BaseModel, UUID4, HttpUrl
from datetime import datetime
from typing import Optional, List

class ImageBase(BaseModel):
    image_url: HttpUrl

class ImageCreate(ImageBase):
    pass

# Add new schema
class ImageUrlRequest(BaseModel):
    image_url: str

class ImageResponse(ImageBase):
    id: UUID4
    session_id: UUID4
    status: str
    created_at: datetime
    updated_at: datetime
    json_data: Optional[dict] = None

    class Config:
        from_attributes = True

class SessionImagesResponse(BaseModel):
    session_id: UUID4
    status: str
    image_urls: List[str]
    total_images: int

    class Config:
        from_attributes = True 