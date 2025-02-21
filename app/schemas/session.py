from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional, List, Dict
from .image import ImageResponse
from uuid import UUID

class SessionBase(BaseModel):
    note: Optional[str] = None
    policy_type: Optional[str] = None

class SessionCreate(SessionBase):
    responsible_id: Optional[int] = None
    partner_channel_id: Optional[int] = None
    responsible_name: Optional[str] = None
    partner_channel_name: Optional[str] = None

class ListSessionResponse(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None
    id_keycloak: Optional[str] = None
    note: Optional[str] = None
    image_status_counts: Optional[Dict[str, int]] = None

    class Config:
        from_attributes = True

class SessionResponse(SessionBase):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    responsible_id: Optional[int] = None
    responsible_name: Optional[str] = None
    partner_channel_id: Optional[int] = None
    partner_channel_name: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None
    images: Optional[List[ImageResponse]] = None

    class Config:
        from_attributes = True

class SessionClose(SessionBase):
    id: UUID

    class Config:
        from_attributes = True

class SessionUpdate(SessionBase):
    status: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None

class SessionListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    data: List[ListSessionResponse]

    class Config:
        from_attributes = True 