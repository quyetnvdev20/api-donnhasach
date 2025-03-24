from pydantic import BaseModel, HttpUrl
from typing import Optional
from app.config import ClaimImageStatus
from datetime import datetime


class CreateInvitationRequest(BaseModel):
    assessment_id: int
    expert_name: str
    expert_phone: str


class CreateInvitationDetail(BaseModel):
    invitation_code: str
    invitation_id: int
    expire_at: str
    deeplink: str


class CreateInvitationResponse(BaseModel):
    data: CreateInvitationDetail
    status: str = ""


class ValidateInvitationRequest(BaseModel):
    invitation_code: str

class SaveImageRequest(BaseModel):
    face_image_url: str
    capture_time: str
    invitation_id: int


class SaveImageResponse(BaseModel):
    id: int


class ValidateInvitationDetail(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int
    assessment_id: int
    invitation_id: int


class ValidateInvitationResponse(BaseModel):
    data: ValidateInvitationDetail


class DoneInvitationRequest(BaseModel):
    assessment_id: int
    invitation_id: int


class CancelInvitationRequest(BaseModel):
    id: int


class CancelInvitationResponse(BaseModel):
    status: str = "success"


class ActionInvitationDetail(BaseModel):
    id: int


class ActionInvitationResponse(BaseModel):
    data: ActionInvitationDetail