from fastapi import APIRouter, Depends, HTTPException, status, Body
from ....schemas.master_data import GarageListResponse
from ....utils.erp_db import PostgresDB
from typing import Optional
import logging
router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/garages", response_model=GarageListResponse)
async def get_garage_list(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
):
    """
    Lấy danh sách gara
    
    Parameters:
    - search: Từ khóa tìm kiếm theo tên gara
    - offset: Vị trí bắt đầu
    - limit: Số lượng bản ghi trả về
    
    Returns:
    - Danh sách gara
    """
    try:
        # Truy vấn để lấy danh sách gara
        query = """
        SELECT 
            rpg.id, 
            rpg.display_name as name, 
            rp.street
        FROM 
            res_partner_gara rpg
        LEFT JOIN 
            res_partner rp ON rp.id = rpg.partner_id
        WHERE 
            1=1
        """
        
        params = []
        
        if search:
            query += " AND (LOWER(rpg.display_name) LIKE $1)"
            params.append(f"%{search.lower()}%")
        
        # Thêm sắp xếp và phân trang
        query += """
        ORDER BY rpg.display_name
        LIMIT ${}
        OFFSET ${}
        """.format(len(params) + 1, len(params) + 2)
        
        params.extend([limit, offset])
        
        result = await PostgresDB.execute_query(query, params)
        
        if not result:
            return {"data": []}
        
        # Chuyển đổi kết quả thành danh sách GarageItem
        garage_items = []
        for item in result:
            garage_items.append({
                "id": item.get('id'),
                "name": item.get('name'),
                "street": item.get('street'),
            })
        
        return {"data": garage_items}
    
    except Exception as e:
        logger.error(f"Error getting garage list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting garage list: {str(e)}"
        )