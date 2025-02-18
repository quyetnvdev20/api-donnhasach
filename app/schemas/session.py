from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional, List
from .image import ImageResponse

class SessionBase(BaseModel):
    note: Optional[str] = None

class SessionCreate(SessionBase):
    pass

class SessionResponse(SessionBase):
    id: UUID4
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None
    images: Optional[List[ImageResponse]] = []

    class Config:
        from_attributes = True

class SessionUpdate(SessionBase):
    status: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None 