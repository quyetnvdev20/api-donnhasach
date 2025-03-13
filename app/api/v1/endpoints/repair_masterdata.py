from fastapi import APIRouter, Depends, HTTPException, status, Body
from ....schemas.repair import RepairCategoryResponse
from ....schemas.master_data import GarageListResponse
from ....utils.erp_db import PostgresDB
from typing import Optional
import logging
router = APIRouter()
logger = logging.getLogger(__name__)



@router.get("/{solution_repair_id}/list-category", response_model=RepairCategoryResponse)
async def get_list_category_repair(
    solution_repair_id: int,
):
    """
    Lấy danh sách hạng mục xe từ line của bảng giám định chi tiết
    
    Parameters:
    - solution_repair_id: ID của phương án sửa chữa
    
    Returns:
    - Danh sách các hạng mục xe
    """
    try:
        # Truy vấn để lấy danh sách hạng mục xe từ phương án sửa chữa
        query = """
        SELECT 
            iclc.id,
            iclc.name,
            iclc.code
        FROM 
            insurance_claim_list_category iclc
        LEFT JOIN 
            insurance_claim_attachment_category icac ON icac.category_id = iclc.id
        where icac.detail_category_id in 
        (SELECT detailed_appraisal_id from insurance_claim_solution_repair where id=$1)
        """
        
        result = await PostgresDB.execute_query(query, [solution_repair_id])
        
        if not result:
            return {"data": []}
        
        # Chuyển đổi kết quả thành danh sách RepairCategory
        repair_items = []
        for item in result:
            repair_items.append({
                    "id": item.get('id'),
                    "name": item.get('name'),
                    "code": item.get('code')
                }   
            )
        
        return {"data": repair_items}
    
    except Exception as e:
        logger.error(f"Error getting repair items: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting repair items: {str(e)}"
        )

