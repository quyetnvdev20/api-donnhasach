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
    try:
        logger.info(f"Starting login for phone: {request.phone}")
        result = await AuthorizationService.login_user(request.dict())
        logger.info(f"Login successful for phone: {request.phone}")
        return result
    except Exception as e:
        logger.error(f"Login error for phone {request.phone}: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi đăng nhập: Thông tin tài khoản không chính xác"
        )

