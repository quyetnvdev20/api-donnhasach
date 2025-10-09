from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class RegisterRequest(BaseModel):
    name: str
    phone: str
    email: str
    password: str
    street: str
    ward_id: int
    state_id: int

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


