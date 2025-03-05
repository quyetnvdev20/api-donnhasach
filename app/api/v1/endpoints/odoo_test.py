from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional, Dict, Any
import json
from app.config import settings, odoo
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/search")
async def search_odoo(
    model: str = Query(..., description="Tên model Odoo (ví dụ: res.partner)"),
    domain: str = Query("[]", description="Domain tìm kiếm dạng JSON string (ví dụ: [[\"is_company\", \"=\", true]])"),
    fields: Optional[str] = Query(None, description="Danh sách các trường cần lấy dạng JSON array (ví dụ: [\"name\", \"email\"])"),
    limit: Optional[int] = Query(10, description="Số lượng bản ghi tối đa"),
    offset: Optional[int] = Query(0, description="Vị trí bắt đầu"),
    order: Optional[str] = Query(None, description="Sắp xếp (ví dụ: id desc)")
):
    """
    API để test hàm search của Odoo ORM
    """
    try:
        # Parse domain từ string sang list
        domain_list = json.loads(domain)
        
        # Parse fields nếu có
        fields_list = None
        if fields:
            fields_list = json.loads(fields)
        
        # Gọi hàm search_method của Odoo
        result = await odoo.search_method(
            model=model,
            domain=domain_list,
            fields=fields_list,
            limit=limit,
            offset=offset,
            order=order
        )
        
        return {
            "success": True,
            "model": model,
            "domain": domain_list,
            "fields": fields_list,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error searching Odoo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching Odoo: {str(e)}")

@router.get("/search_ids")
async def search_ids_odoo(
    model: str = Query(..., description="Tên model Odoo (ví dụ: res.partner)"),
    domain: str = Query("[]", description="Domain tìm kiếm dạng JSON string (ví dụ: [[\"is_company\", \"=\", true]])"),
    limit: Optional[int] = Query(10, description="Số lượng bản ghi tối đa"),
    offset: Optional[int] = Query(0, description="Vị trí bắt đầu"),
    order: Optional[str] = Query(None, description="Sắp xếp (ví dụ: id desc)")
):
    """
    API để test hàm search_ids của Odoo ORM (chỉ trả về ID)
    """
    try:
        # Parse domain từ string sang list
        domain_list = json.loads(domain)
        
        # Gọi hàm search_ids của Odoo
        result = await odoo.search_ids(
            model=model,
            domain=domain_list,
            limit=limit,
            offset=offset,
            order=order
        )
        
        return {
            "success": True,
            "model": model,
            "domain": domain_list,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error searching Odoo IDs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching Odoo IDs: {str(e)}") 