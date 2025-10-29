from fastapi import APIRouter, HTTPException, Query, Path,Depends,Header, Body
from typing import Optional
import logging
from typing import List, Optional, Dict, Any, Annotated
from datetime import datetime
from .masterdatas_service import MasterdatasService
from app.api.deps import verify_signature
from app.schemas.common_schema import CommonHeaderPortal

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
async def get_booking(
        headers: Annotated[CommonHeaderPortal, Header()],
        limit: int = 10,
        page: int = 1,
        search: Optional[str] = None,
        _=Depends(verify_signature),
):
    try:
        result = await MasterdatasService.get_state(page, limit, search)

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
            detail="Có lỗi xảy ra khi lấy danh sách tỉnh thành phố"
        )