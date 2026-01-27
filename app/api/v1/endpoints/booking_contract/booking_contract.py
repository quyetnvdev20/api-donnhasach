from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional
import logging
from app.api.deps import get_current_user
from .booking_contract_service import BookingContractService
from app.schemas.booking_contract_schema import BookingContractCreateRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", summary="Tạo hợp đồng dọn dẹp định kỳ")
async def create_booking_contract_post(
        current_user=Depends(get_current_user),
        request: BookingContractCreateRequest = Body(...),
):
    try:
        result = await BookingContractService.create_booking_contract(request.dict(), current_user)
        return {
            "success": True,
            "message": "Tạo hợp đồng định kỳ thành công",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_booking_contract: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi tạo hợp đồng định kỳ"
        )

