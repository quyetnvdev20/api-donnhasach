from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from ....schemas.masterdata import GarageListResponse, BranchListResponse, AppraiserListResponse
from ....utils.erp_db import PostgresDB
from typing import Optional, Annotated
import logging
from ...deps import get_current_user
from ....config import settings, odoo
from ....utils.distance_calculator import find_nearby_garages
from ....schemas.common import CommonHeaders
router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/garages", response_model=GarageListResponse)
async def get_garage_list(
    headers: Annotated[CommonHeaders, Header()],
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
):
    
    # TODO: Remove this after testing Latitude and Longitude Tasco
    latitude = headers.latitude or 21.015853129655014
    longitude = headers.longitude or 105.78303779624088
    """
    Lấy danh sách gara
    
    Parameters:
    - search: Từ khóa tìm kiếm theo tên gara
    - offset: Vị trí bắt đầu
    - limit: Số lượng bản ghi trả về
    - radius_km: Bán kính tìm kiếm tính bằng km (mặc định là 20km)
    
    Returns:
    - Danh sách gara được sắp xếp theo khoảng cách từ gần đến xa, với phân trang
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
            rp.active = true
        """
        
        params = []
        
        if search:
            query += " AND (LOWER(rpg.display_name) LIKE $1)"
            params.append(f"%{search.lower()}%")
        # TODO: Remove this after testing Latitude and Longitude Tasco
        query += " order by rpg.id desc limit 1000"

        # Thực hiện truy vấn để lấy tất cả gara phù hợp với điều kiện tìm kiếm
        result = await PostgresDB.execute_query(query, params)
        
        if not result:
            return {"data": [], "total": 0, "offset": offset, "limit": limit}
        
        # Tạo danh sách gara cần kiểm tra khoảng cách
        garage_items_check = []
        for item in result:
            garage_items_check.append({
                'id': item.get('id'),
                'address': item.get('street', ''),
                'name': item.get('name', '')
            })

        # Tính khoảng cách và sắp xếp theo khoảng cách từ gần đến xa
        distances = await find_nearby_garages(
            float(latitude), 
            float(longitude), 
            garage_items_check
        )
        
        if distances:
            # Trả về danh sách đã sắp xếp theo khoảng cách
            all_garage_items = []
            for garage_id, garage_info in distances.items():
                all_garage_items.append({
                    "id": garage_id,
                    "name": garage_info.get('name'),
                    "street": garage_info.get('address'),
                    "distance": garage_info.get('distance', 0),
                    "travel_time_minutes": garage_info.get('travel_time_minutes', 0)
                })
            
            # Tính tổng số gara
            total_garages = len(all_garage_items)
            
            
            # Áp dụng phân trang
            start_idx = min(offset * limit, total_garages)
            end_idx = min(offset * limit + limit, total_garages)
            paginated_garage_items = all_garage_items[start_idx:end_idx]
            
            return {
                "data": paginated_garage_items,
                
            }
        return {"data": []}
    
    except Exception as e:
        logger.error(f"Error getting garage list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting garage list: {str(e)}"
        )
    

@router.get("/branches", response_model=BranchListResponse)
async def get_branch_list(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
):
    """
    Lấy danh sách chi nhánh
    
    Parameters:
    - search: Từ khóa tìm kiếm theo tên hoặc mã chi nhánh
    - offset: Vị trí bắt đầu
    - limit: Số lượng bản ghi trả về
    
    Returns:
    - Danh sách chi nhánh
    """
    try:
        # Truy vấn để lấy danh sách chi nhánh
        query = """
        SELECT 
            rb.id, 
            rb.name, 
            rb.code
        FROM 
            res_branch rb
        WHERE 
            1=1
        """
        
        params = []
        
        if search:
            query += " AND (LOWER(rb.name) LIKE $1"
            params.append(f"%{search.lower()}%")
        
        # Thêm sắp xếp và phân trang
        query += """
        ORDER BY rb.name
        LIMIT ${}
        OFFSET ${}
        """.format(len(params) + 1, len(params) + 2)
        
        params.extend([limit, offset])
        
        result = await PostgresDB.execute_query(query, params)
        
        if not result:
            return {"data": []}
        
        # Chuyển đổi kết quả thành danh sách BranchItem
        branch_items = []
        for item in result:
            branch_items.append({
                "id": item.get('id'),
                "name": item.get('name'),
                "code": item.get('code'),
            })
        
        return {"data": branch_items}
    
    except Exception as e:
        logger.error(f"Error getting branch list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting branch list: {str(e)}"
        )
    

@router.get("/appraisers", response_model=AppraiserListResponse)
async def get_appraisers(
    branch_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Lấy danh sách giám định viên
    
    Parameters:
    - search: Từ khóa tìm kiếm theo tên giám định viên
    - branch_id: ID của chi nhánh
    - offset: Vị trí bắt đầu
    - limit: Số lượng bản ghi trả về
    
    Returns:
    - Danh sách giám định viên
    """
    try:
        # Gọi API của Odoo để lấy danh sách giám định viên

        response = await odoo.call_method_not_record(
            model='res.users',
            method='get_claim_staff_user_api',
            token=current_user.odoo_token,
            kwargs={'branch_id': branch_id}
        )

        if not response:
            return {"data": []}
        
        # Chuyển đổi kết quả thành danh sách AppraiserItem
        appraiser_items = []
        for item in response:
            appraiser_items.append({
                "id": item.get('id'),
                "name": item.get('name')
            })
        
        return {"data": appraiser_items}
    
    except Exception as e:
        logger.error(f"Error getting appraisers list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting appraisers list: {str(e)}"
        )
