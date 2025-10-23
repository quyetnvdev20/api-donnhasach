from fastapi import APIRouter, HTTPException, Query, Path,Depends,Header
from typing import Optional
import logging
from typing import List, Optional, Dict, Any, Annotated
from app.api.deps import get_current_user
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