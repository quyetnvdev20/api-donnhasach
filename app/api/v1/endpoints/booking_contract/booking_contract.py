from fastapi import APIRouter, HTTPException, Depends, Body, Path, Query
from typing import Optional
import logging
from datetime import datetime
from app.api.deps import get_current_user
from .booking_contract_service import BookingContractService
from app.api.v1.endpoints.payment.payment_service import PaymentService
from app.api.v1.endpoints.booking.booking_service import BookingService
from app.schemas.booking_contract_schema import CreatePayOSPaymentRequest
from app.schemas.booking_contract_schema import (
    BookingContractCreateRequest, 
    BookingContractScheduleUpdateRequest, 
    BookingContractCheckPriceRequest
)
from app.schemas.booking_schema import CalculateCleaningDatesRequest

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


@router.post("/{contract_id}/payos/create-payment", summary="Tạo payment link từ PayOS")
async def create_payos_payment(
        contract_id: int = Path(..., description="ID hợp đồng"),
        payment_method_id: int = Body(..., description="ID phương thức thanh toán"),
        return_url: Optional[str] = Body(None, description="URL redirect sau khi thanh toán thành công"),
        cancel_url: Optional[str] = Body(None, description="URL redirect khi hủy thanh toán"),
        current_user=Depends(get_current_user),
):
    """
    Tạo payment link từ PayOS cho hợp đồng
    """
    try:
        result = await PaymentService.create_payos_payment_contract_link(
            contract_id=contract_id,
            payment_method_id=payment_method_id,
            current_user=current_user,
            return_url=return_url,
            cancel_url=cancel_url,
        )
        
        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', 'Lỗi không xác định'))
        
        return {
            "success": True,
            "message": "Tạo payment link thành công",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_payos_payment: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi tạo payment link"
        )


@router.get("/{contract_id}/payos/status", summary="Lấy trạng thái thanh toán")
async def get_payment_status(
        contract_id: int = Path(..., description="ID hợp đồng"),
        current_user=Depends(get_current_user),
):
    """
    Lấy trạng thái thanh toán của hợp đồng
    """
    try:
        result = await PaymentService.get_payment_status(
            contract_id=contract_id,
            current_user=current_user,
        )
        
        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', 'Lỗi không xác định'))
        
        return {
            "success": True,
            "message": "Lấy trạng thái thanh toán thành công",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_payment_status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy trạng thái thanh toán"
        )


@router.post("/periodic/calculate-dates", summary="Tính các ngày dọn dẹp định kỳ")
async def calculate_cleaning_dates(
        current_user=Depends(get_current_user),
        request: CalculateCleaningDatesRequest = Body(...),
):
    try:
        result = await BookingService.calculate_cleaning_dates(
            weekdays=request.weekdays,
            package_id=request.package_id,
            start_date=request.start_date
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Có lỗi xảy ra khi tính ngày dọn dẹp")
            )
        
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in calculate_cleaning_dates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi tính ngày dọn dẹp"
        )



