from fastapi import APIRouter, HTTPException, Query, Path,Depends,Header, Body
from typing import Optional
import logging
from typing import List, Optional, Dict, Any, Annotated
from app.api.deps import get_current_user
from .booking_service import BookingService
from datetime import datetime
from app.config import BOOKING_HOURS, APPOINTMENT_DURATION, QUANTITY, TIME_OPTIONS, EMPLOYEE_QUANTITY
from app.schemas.booking_schema import (
    BookingCalculateRequest,
    BookingCreateRequest, 
    BookingCancelRequest,
    PeriodicPricingRequest,
    PeriodicBookingCreateRequest,
)
from app.api.v1.endpoints.payment.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", summary="Lấy danh sách lịch đã đặt")
async def get_booking(
        limit: int = 10,
        page: int = 1,
        cleaning_state: str = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        current_user=Depends(get_current_user),
):
    try:
        result = await BookingService.get_booking(current_user, page, limit, from_date, to_date, cleaning_state)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return {
            "success": True,
            "message": "Lấy danh sách lịch hẹn",
            "data": result["data"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách nhân viên có sẵn"
        )



@router.post("/", summary="Đặt lịch dọn dẹp")
async def create_event_post(
        current_user=Depends(get_current_user),
        request: BookingCreateRequest =Body(...),
):
    try:
        result = await BookingService.create_event(request.dict(), current_user)
        return {
            "success": True,
            "message": "Đặt lịch thành công",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in calculate: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi đặt lịch"
        )

@router.post("/pricing/calculate", summary="Tính giá dịch vụ")
async def pricing_calculate(
        current_user=Depends(get_current_user),
        request: BookingCalculateRequest =Body(...),
):
    try:
        result = await BookingService.get_pricing_calculate(request.dict(), current_user)
        return {
            "success": True,
            "message": "Tính giá dịch vụ thành công",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in calculate: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lính giá dịch vụ"
        )

@router.get("/state", summary="Lấy danh sách trạng thái đặt lịch")
async def get_booking(
        current_user=Depends(get_current_user),
):
    try:
        result = await BookingService.get_value_state()

        return {
            "success": True,
            "message": "Lấy danh sách trạng thái đặt lịch",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách trạng thái đặt lịch"
        )


@router.get("/{booking_id}", summary="Lấy chi tiết lịch hẹn")
async def get_blog_post_detail(
        booking_id: int = Path(..., gt=0, description="ID của lịch hẹn"),
        current_user=Depends(get_current_user),
):
    try:
        # Lấy chi tiết lịch hẹn
        result = await BookingService.get_booking_detail(booking_id)

        if not result["success"]:
            if result["error"] == "Không tìm thấy lịch hẹn":
                raise HTTPException(
                    status_code=404,
                    detail="Không tìm thấy lịch hẹn"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=result["error"]
                )

        data = result["data"]
        return {
            "success": True,
            "message": "Lấy chi tiết lịch hẹn thành công",
            "data": data,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_blog_post_detail: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy chi tiết lịch hẹn"
        )

@router.post("/cancel", summary="Hủy đặt lịch dọn dẹp")
async def cancel_booking_post(
        current_user=Depends(get_current_user),
        request: BookingCancelRequest = Body(...),
):
    try:
        result = await BookingService.cancel_booking(request.dict())
        return {
            "success": True,
            "message": "Hủy đặt lịch thành công",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in calculate: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi hủy đặt lịch"
        )

@router.post("/periodic/calculate-pricing", summary="Tính giá cho lịch định kỳ")
async def calculate_periodic_pricing(
        current_user=Depends(get_current_user),
        request: PeriodicPricingRequest = Body(...),
):
    try:
        result = await BookingService.calculate_periodic_pricing(request.dict(), current_user)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Có lỗi xảy ra khi tính giá định kỳ")
            )
        
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in calculate_periodic_pricing: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi tính giá định kỳ"
        )


@router.post("/{booking_id}/payos/create-payment", summary="Tạo payment link từ PayOS cho booking")
async def create_payos_payment_booking(
        booking_id: int = Path(..., description="ID booking"),
        payment_method_id: int = Body(..., description="ID phương thức thanh toán"),
        return_url: Optional[str] = Body(None, description="URL redirect sau khi thanh toán thành công"),
        cancel_url: Optional[str] = Body(None, description="URL redirect khi hủy thanh toán"),
        current_user=Depends(get_current_user),
):
    """
    Tạo payment link từ PayOS cho booking (calendar.event)
    """
    try:
        result = await PaymentService.create_payos_payment_link_booking(
            booking_id=booking_id,
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
        logger.error(f"Unexpected error in create_payos_payment_booking: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi tạo payment link"
        )


@router.get("/{booking_id}/payos/status", summary="Lấy trạng thái thanh toán của booking")
async def get_payment_status_booking(
        booking_id: int = Path(..., description="ID booking"),
        current_user=Depends(get_current_user),
):
    """
    Lấy trạng thái thanh toán của booking (calendar.event)
    """
    try:
        result = await PaymentService.get_payment_status_booking(
            booking_id=booking_id,
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
        logger.error(f"Unexpected error in get_payment_status_booking: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy trạng thái thanh toán"
        )


