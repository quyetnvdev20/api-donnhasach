from fastapi import APIRouter, HTTPException, Query, Path,Depends,Header
from typing import Optional
import logging
from typing import List, Optional, Dict, Any, Annotated
from app.api.deps import get_current_user
from .employee_service import EmployeeService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/available", summary="Lấy danh sách nhân viên có sẵn")
async def get_employee_available(
        categ_id: int,
        current_user=Depends(get_current_user),
):
    try:
        result = await EmployeeService.get_employee_available(categ_id, current_user)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return {
            "success": True,
            "message": "Lấy danh sách nhân viên có sẵn",
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