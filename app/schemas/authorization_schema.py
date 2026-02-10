from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class RegisterRequest(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    password: str
    street: Optional[str] = None
    ward_id: Optional[int] = None
    state_id: Optional[int] = None

class DeviceLoginRequest(BaseModel):
    phone: str
    device_id: str


class LoginRequest(BaseModel):
    phone: str
    device_id: str
    password: str

class UserObject(BaseModel):
    token: str
    uid: str

class SendOTPRequest(BaseModel):
    phone: str

class VerifyOTPRequest(BaseModel):
    phone: str
    otp_code: str
    device_id: Optional[str] = None

class ZaloMiniappLoginRequest(BaseModel):
    phone: str
    name: str
    zalo_id: str
    device_id: Optional[str] = None

class ZaloPhoneTokenRequest(BaseModel):
    token: str  # Token từ getPhoneNumber() của Zalo SDK


