from fastapi import APIRouter, HTTPException, Query, Path, Depends, Header, Body
from typing import Optional
import logging
from app.api.deps import get_current_user
from .loyalty_service import LoyaltyService
from app.schemas.loyalty_schema import LoyaltyProgramsRequest, LoyaltyProgramByCardRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/programs", summary="Lấy danh sách các chính sách bán hàng và chương trình khuyến mại")
async def get_loyalty_programs(
        current_user=Depends(get_current_user),
        request: LoyaltyProgramsRequest = Body(...),
):
    """
    API lấy danh sách các chính sách bán hàng và chương trình khuyến mại
    dựa vào categ_id, appointment_duration, amount_total, date
    """
    try:
        result = await LoyaltyService.get_loyalty_programs(request.dict(), current_user)
        return {
            "success": True,
            "message": "Lấy danh sách chương trình khuyến mại thành công",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_loyalty_programs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách chương trình khuyến mại"
        )


@router.post("/program-by-card", summary="Lấy chương trình khuyến mại theo mã phiếu giảm giá")
async def get_loyalty_program_by_card(
        current_user=Depends(get_current_user),
        request: LoyaltyProgramByCardRequest = Body(...),
):
    """
    API lấy chương trình khuyến mại dựa vào mã loyalty card và kiểm tra điều kiện
    dựa vào code, categ_id (optional), appointment_duration, amount_total, date
    """
    try:
        result = await LoyaltyService.get_loyalty_program_by_card(request.dict(), current_user)
        return {
            "success": True,
            "message": "Lấy thông tin chương trình khuyến mại thành công",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_loyalty_program_by_card: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy thông tin chương trình khuyến mại"
        )
