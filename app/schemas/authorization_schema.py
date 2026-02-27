from pydantic import BaseModel, HttpUrl, model_validator
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
    """Phone trực tiếp HOẶC token + access_token (backend gọi Zalo graph API để đổi token → số điện thoại)."""
    phone: Optional[str] = None
    token: Optional[str] = None  # Token từ getPhoneNumber() của Zalo SDK
    access_token: Optional[str] = None  # Từ sdk.getAccessToken() trên miniapp
    name: str
    zalo_id: str
    device_id: Optional[str] = None

    @model_validator(mode="after")
    def require_phone_or_token(self):
        if self.phone:
            return self
        if self.token and self.access_token:
            return self
        raise ValueError("Cần truyền phone HOẶC (token và access_token)")


class ZaloPhoneTokenRequest(BaseModel):
    token: str  # Token từ getPhoneNumber() của Zalo SDK


