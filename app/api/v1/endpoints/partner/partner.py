from fastapi import APIRouter, HTTPException, Query, Path,Depends,Header, Body
from typing import Optional
import logging
from typing import List, Optional, Dict, Any, Annotated
from app.api.deps import get_current_user
from app.schemas.partner_schema import ContactPartnerRequest
from .partner_service import PartnerService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me", summary="Lấy thông tin khách hàng đang đăng nhập")
async def get_info_me(
        current_user=Depends(get_current_user),
):
    try:
        result = await PartnerService.get_current_partner(current_user)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return {
            "success": True,
            "message": "Lấy thông tin khách hàng đang đăng nhập",
            "data": result["data"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy thông tin khách hàng đang đăng nhập"
        )

@router.get("/contact", summary="Lấy danh sách thông tin liên hệ khách hàng")
async def get_contact_partner(
        current_user=Depends(get_current_user),
):
    try:
        result = await PartnerService.get_add_partner(current_user)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return {
            "success": True,
            "message": "Lấy danh sách thông tin liên hệ khách hàng",
            "data": result["data"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách thông tin liên hệ khách hàng"
        )

@router.post("/contact", summary="Tạo liên hệ khách hàng")
async def create_contact_partner(
        current_user=Depends(get_current_user),
        request: ContactPartnerRequest =Body(...),
):
    try:
        result = await PartnerService.create_contact_partner(request.dict(), current_user)
        return {
            "success": True,
            "message": "Tạo địa chỉ khách hàng thành công",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in calculate: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi tạo liên hệ"
        )
@router.put("/contact/{contact_id}", summary="Cập nhật liên hệ khách hàng")
async def update_contact_partner(
        current_user=Depends(get_current_user),
        request: ContactPartnerRequest =Body(...),
        contact_id: int = Path(..., gt=0, description="ID của liên hệ"),
):
    try:
        result = await PartnerService.update_contact_partner(request.dict(), contact_id, current_user)
        return {
            "success": True,
            "message": "Cập nhật địa chỉ khách hàng thành công",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in calculate: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi cập nhật liên hệ"
        )