from fastapi import APIRouter, HTTPException, Query, Path,Depends,Header
from typing import Optional
import logging
from app.api.deps import verify_signature
from .pricelist_service import PriceListSerivce
from typing import List, Optional, Dict, Any, Annotated
from app.schemas.common_schema import CommonHeaderPortal

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", summary="Lấy danh sách bảng giá")
async def get_pricelist(
        headers: Annotated[CommonHeaderPortal, Header()],
        _=Depends(verify_signature),
):
    try:
        result = await PriceListSerivce.get_pricelist()

        return {
            "success": True,
            "message": "Lấy danh sách bảng giá thành công",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách bảng giá"
        )