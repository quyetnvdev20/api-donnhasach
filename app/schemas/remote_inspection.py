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
    expire_at: str


class CreateInvitationResponse(BaseModel):
    data: CreateInvitationDetail
    status: str = ""


class ValidateInvitationRequest(BaseModel):
    invitation_code: str
    face_image_url: str
    capture_time: str


class ValidateInvitationDetail(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    assessment_id: int


class ValidateInvitationResponse(BaseModel):
    data: ValidateInvitationDetail


class ActionInvitationRequest(BaseModel):
    invitation_code: str
    assessment_id: int


class ActionInvitationDetail(BaseModel):
    id: int


class ActionInvitationResponse(BaseModel):
    data: ActionInvitationDetail