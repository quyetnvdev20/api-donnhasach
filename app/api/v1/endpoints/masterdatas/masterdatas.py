from fastapi import APIRouter, HTTPException, Query, Path,Depends,Header, Body
from typing import Optional
import logging
from typing import List, Optional, Dict, Any, Annotated
from datetime import datetime
from .masterdatas_service import MasterdatasService
from app.api.deps import verify_signature
from app.schemas.common_schema import CommonHeaderPortal
from app.config import BOOKING_HOURS, APPOINTMENT_DURATION, QUANTITY, TIME_OPTIONS, EMPLOYEE_QUANTITY, WEEKDAYS
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ward", summary="Lấy danh sách xã phường")
async def get_booking(
        headers: Annotated[CommonHeaderPortal, Header()],
        limit: int = 10,
        page: int = 1,
        state_id: int = None,
        search: Optional[str] = None,
        _=Depends(verify_signature),
):
    try:
        result = await MasterdatasService.get_ward(page, limit, search,state_id)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách xã phường"
        )

@router.get("/state", summary="Lấy danh sách tỉnh thành phố")
async def get_state(
        headers: Annotated[CommonHeaderPortal, Header()],
        limit: int = 10,
        page: int = 1,
        search: Optional[str] = None,
        _=Depends(verify_signature),
):
    try:
        logger.info(f"Getting states with params: page={page}, limit={limit}, search={search}")
        result = await MasterdatasService.get_state(page, limit, search)
        logger.info(f"States result: success={result.get('success')}, total={result.get('total')}, data_count={len(result.get('data', []))}")

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_state: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách tỉnh thành phố"
        )

@router.get("/hours", summary="Lấy danh sách giờ dịch vụ")
async def get_booking_hours(
        current_user=Depends(get_current_user),
):
    try:
        return {
            "success": True,
            "message": "Lấy danh sách giờ dịch vụ thành công",
            "data": BOOKING_HOURS,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách giờ dịch vụ"
        )

@router.get("/duration", summary="Lấy danh sách thời gian dịch vụ")
async def get_booking_duration(
        current_user=Depends(get_current_user),
):
    try:
        return {
            "success": True,
            "message": "Lấy danh sách thời gian dịch vụ",
            "data": APPOINTMENT_DURATION,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách thời gian dịch vụ"
        )

@router.get("/quantity", summary="Lấy danh sách số lượng")
async def get_booking_quantity(
        current_user=Depends(get_current_user),
):
    try:
        return {
            "success": True,
            "message": "Lấy danh sách số lượng",
            "data": QUANTITY,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách số lượng"
        )


@router.get("/recurring-unit", summary="Lấy danh sách đơn vị lịch hẹn")
async def get_booking_quantity(
        current_user=Depends(get_current_user),
):
    try:
        return {
            "success": True,
            "message": "Lấy danh sách đơn vị lịch hẹn",
            "data": TIME_OPTIONS,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách đơn vị lịch hẹn"
        )

@router.get("/recurring-unit", summary="Lấy danh sách đơn vị lịch hẹn")
async def get_booking_quantity(
        current_user=Depends(get_current_user),
):
    try:
        return {
            "success": True,
            "message": "Lấy danh sách đơn vị lịch hẹn",
            "data": TIME_OPTIONS,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách đơn vị lịch hẹn"
        )
    
@router.get("/employee-quantity", summary="Lấy danh sách số lượng nhân viên")
async def get_employee_quantity(
        current_user=Depends(get_current_user),
):
    try:
        return {
            "success": True,
            "message": "Lấy danh sách số lượng nhân viên",
            "data": EMPLOYEE_QUANTITY,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách số lượng nhân viên"
        )

@router.get("/periodic-packages", summary="Lấy danh sách gói định kỳ")
async def get_periodic_packages(
        current_user=Depends(get_current_user),
):
    try:
        result = await MasterdatasService.get_periodic_packages()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Có lỗi xảy ra khi lấy danh sách gói định kỳ")
            )
        
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_periodic_packages: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách gói định kỳ"
        )

@router.get("/weekdays", summary="Lấy danh sách thứ trong tuần")
async def get_weekdays(
        current_user=Depends(get_current_user),
):
    try:
        return {
            "success": True,
            "message": "Lấy danh sách thứ trong tuần thành công",
            "data": WEEKDAYS,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_weekdays: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách thứ trong tuần"
        )

@router.get("/payment-methods", summary="Lấy danh sách phương thức thanh toán")
async def get_payment_methods(
        is_periodic: bool = Query(False, description="Là gói định kỳ (chỉ trả về chuyển khoản). Giá trị: true hoặc false"),
        current_user=Depends(get_current_user),
):
    try:
        # FastAPI tự động convert query string sang boolean
        result = await MasterdatasService.get_payment_methods(is_periodic=is_periodic)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Có lỗi xảy ra khi lấy danh sách phương thức thanh toán")
            )
        
        return {
            "success": True,
            "message": "Lấy danh sách phương thức thanh toán thành công",
            "data": result["data"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_payment_methods: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách phương thức thanh toán"
        )