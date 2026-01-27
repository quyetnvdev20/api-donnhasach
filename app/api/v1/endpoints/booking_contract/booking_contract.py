from fastapi import APIRouter, HTTPException, Depends, Body, Path, Query
from typing import Optional
import logging
from datetime import datetime
from app.api.deps import get_current_user
from .booking_contract_service import BookingContractService
from app.api.v1.endpoints.payment.payment_service import PaymentService
from app.schemas.booking_contract_schema import (
    BookingContractCreateRequest, 
    BookingContractScheduleUpdateRequest, 
    BookingContractCheckPriceRequest
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", summary="Lấy danh sách hợp đồng định kỳ")
async def get_booking_contracts(
        limit: int = Query(10, ge=1, le=100),
        page: int = Query(1, ge=1),
        state: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        current_user=Depends(get_current_user),
):
    try:
        result = await BookingContractService.get_booking_contracts(
            current_user, page, limit, from_date, to_date, state
        )
        return {
            "success": True,
            "message": "Lấy danh sách hợp đồng định kỳ thành công",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_booking_contracts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách hợp đồng định kỳ"
        )


@router.get("/{contract_id}", summary="Lấy chi tiết hợp đồng định kỳ")
async def get_booking_contract_detail(
        contract_id: int = Path(..., description="ID hợp đồng"),
        current_user=Depends(get_current_user),
):
    try:
        result = await BookingContractService.get_booking_contract_detail(contract_id, current_user)
        
        # Odoo trả về {success: true, data: {...}}, extract data để tránh nested
        if isinstance(result, dict) and result.get("success") and result.get("data"):
            return {
                "success": True,
                "message": "Lấy chi tiết hợp đồng định kỳ thành công",
                "data": result.get("data"),
            }
        else:
            return {
                "success": True,
                "message": "Lấy chi tiết hợp đồng định kỳ thành công",
                "data": result,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_booking_contract_detail: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy chi tiết hợp đồng định kỳ"
        )


@router.post("/check-price", summary="Kiểm tra giá khi đổi lịch")
async def check_schedule_price(
        request: BookingContractCheckPriceRequest = Body(...),
        current_user=Depends(get_current_user),
):
    try:
        result = await BookingContractService.check_schedule_price(
            request.contract_id, request.schedule_id, request.new_date, current_user
        )
        return {
            "success": True,
            "message": "Kiểm tra giá thành công",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in check_schedule_price: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi kiểm tra giá"
        )


@router.put("/{contract_id}/schedule/{schedule_id}", summary="Đổi lịch schedule.booking.calendar")
async def update_schedule_date(
        contract_id: int = Path(..., description="ID hợp đồng"),
        schedule_id: int = Path(..., description="ID schedule"),
        request: BookingContractScheduleUpdateRequest = Body(...),
        current_user=Depends(get_current_user),
):
    try:
        result = await BookingContractService.update_schedule_date(
            contract_id, schedule_id, request.dict(), current_user
        )
        return {
            "success": True,
            "message": "Đổi lịch thành công",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_schedule_date: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi đổi lịch"
        )


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



