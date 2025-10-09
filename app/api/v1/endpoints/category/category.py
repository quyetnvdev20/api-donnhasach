from fastapi import APIRouter, HTTPException, Query, Path,Depends,Header
from typing import Optional
import logging
from typing import List, Optional, Dict, Any, Annotated
from app.api.deps import verify_signature
from app.schemas.common_schema import CommonHeaderPortal
from .category_service import CategoryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", summary="Lấy danh sách loại dịch vụ")
async def get_category(
        headers: Annotated[CommonHeaderPortal, Header()],
        search: Optional[str] = None,
        limit: int = 10,
        page: int = 1,
        _=Depends(verify_signature),
):
    try:
        result = await CategoryService.get_category_service(
            page=page,
            limit=limit,
            search=search
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return {
            "success": True,
            "message": "Lấy danh sách danh mục dịch vụ",
            "data": result["data"],
            "current_page": result["current_page"],
            "limit": result["limit"],
            "total": result["total"],
            "total_pages": result["total_pages"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách danh mục dịch vụ"
        )