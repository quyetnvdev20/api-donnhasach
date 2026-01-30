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


@router.get("/product-extra", summary="Lấy danh sách sản phẩm dịch vụ thêm")
async def get_product_extra(
        headers: Annotated[CommonHeaderPortal, Header()],
        category_id: int = Query(..., description="ID của category"),
        _=Depends(verify_signature),
):
    try:
        result = await CategoryService.get_product_extra_service(
            category_id=category_id
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return {
            "success": True,
            "message": "Lấy danh sách dịch vụ thêm thành công",
            "data": result["data"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in product-extra: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách dịch vụ thêm"
        )


@router.get("/cleaning-script", summary="Lấy kịch bản dọn nhà theo category")
async def get_cleaning_script(
        headers: Annotated[CommonHeaderPortal, Header()],
        category_id: int = Query(..., description="ID của category"),
        _=Depends(verify_signature),
):
    try:
        result = await CategoryService.get_cleaning_script_service(
            category_id=category_id
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return {
            "success": True,
            "message": "Lấy kịch bản dọn nhà thành công",
            "data": result["data"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in cleaning-script: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy kịch bản dọn nhà"
        )


@router.get("/employee-configs", summary="Lấy danh sách cấu hình nhân viên theo category")
async def get_employee_configs(
        headers: Annotated[CommonHeaderPortal, Header()],
        category_id: int = Query(..., description="ID của category"),
        _=Depends(verify_signature),
):
    try:
        result = await CategoryService.get_employee_configs_service(
            category_id=category_id
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return {
            "success": True,
            "message": "Lấy danh sách cấu hình nhân viên thành công",
            "data": result["data"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in employee-configs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách cấu hình nhân viên"
        )

