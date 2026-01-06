from fastapi import APIRouter, Header, Depends, Body, HTTPException, status
import logging
from typing import List, Optional, Dict, Any, Annotated
from app.schemas.common_schema import CommonHeaderPortal
from app.schemas.authorization_schema import RegisterRequest,DeviceLoginRequest, LoginRequest
from app.api.deps import verify_signature
from .authorization_service import AuthorizationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", summary="Đăng ký")
async def authorization_register(
        headers: Annotated[CommonHeaderPortal, Header()],
        request: RegisterRequest =Body(...),
        _=Depends(verify_signature),
):
    result = await AuthorizationService.register_user_portal(request.dict())
    return result

@router.post("/device-login", summary="Đăng nhập qua device_id")
async def authorization_register(
        headers: Annotated[CommonHeaderPortal, Header()],
        request: DeviceLoginRequest =Body(...),
):
    result = await AuthorizationService.get_device_by_phone_user(request.dict())
    return result

@router.post("/login", summary="Đăng nhập bằng mật khẩu")
async def authorization_login(
        headers: Annotated[CommonHeaderPortal, Header()],
        request: LoginRequest =Body(...),
):
    logger.info(f"Starting login for phone: {request.phone}")
    result = await AuthorizationService.login_user(request.dict())
    logger.info(f"Login successful for phone: {request.phone}")
    return result

