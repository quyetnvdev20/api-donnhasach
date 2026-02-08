from fastapi import APIRouter, Header, Depends, Body, HTTPException, status, Request
import logging
from typing import List, Optional, Dict, Any, Annotated
from app.schemas.common_schema import CommonHeaderPortal
from app.schemas.authorization_schema import RegisterRequest,DeviceLoginRequest, LoginRequest, SendOTPRequest, VerifyOTPRequest
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

@router.post("/send-otp", summary="Gửi mã OTP qua Zalo")
async def send_otp(
        http_request: Request,
        headers: Annotated[CommonHeaderPortal, Header()],
        request: SendOTPRequest = Body(...),
):
    """
    Gửi mã OTP 6 chữ số qua ZNS (Zalo Notification Service) đến số điện thoại
    Mã OTP sẽ được lưu vào Redis với thời gian hết hạn 3 phút
    Rate limit: 3 lần/5 phút, 6 lần/24h cho mỗi số điện thoại
    """
    # Lấy client IP
    client_ip = None
    if http_request:
        # Lấy IP từ header X-Forwarded-For hoặc X-Real-IP (nếu có proxy)
        forwarded_for = http_request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = http_request.headers.get("X-Real-IP") or http_request.client.host
    
    logger.info(f"Sending OTP to phone: {request.phone}, IP: {client_ip}")
    result = await AuthorizationService.send_otp(request.dict(), client_ip=client_ip)
    logger.info(f"OTP sent successfully to phone: {request.phone}")
    return result

@router.post("/verify-otp", summary="Xác thực mã OTP")
async def verify_otp(
        headers: Annotated[CommonHeaderPortal, Header()],
        request: VerifyOTPRequest = Body(...),
):
    """
    Xác thực mã OTP từ Redis
    Sau khi xác thực thành công, mã OTP sẽ bị xóa khỏi Redis
    """
    logger.info(f"Verifying OTP for phone: {request.phone}")
    result = await AuthorizationService.verify_otp(request.dict())
    logger.info(f"OTP verified successfully for phone: {request.phone}")
    return result

