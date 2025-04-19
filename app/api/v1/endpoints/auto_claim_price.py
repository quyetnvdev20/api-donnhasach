from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from ...deps import get_current_user
from typing import Optional, List, Dict, Any
import logging
from app.schemas.auto_claim_price import AutoClaimPriceRequest, AutoClaimPriceResponse
from app.utils.erp_db import PostgresDB
from app.utils.odoo import UserError
router = APIRouter()
logger = logging.getLogger(__name__)

# get id of brand
async def get_brand_id(brand: str):
    normalized_name = brand.lower().strip()
    
    # First try exact match
    query_exact = """
    SELECT id FROM res_car_brand WHERE lower(name) = $1
    """
    brand_id = await PostgresDB.execute_query(query_exact, [normalized_name])
    
    # If exact match not found, try fuzzy search
    if not brand_id:
        # Construct the search pattern with wildcards
        search_pattern = f"%{normalized_name}%"
        query_fuzzy = """
        SELECT id FROM res_car_brand WHERE lower(name) LIKE $1
        """
        brand_id = await PostgresDB.execute_query(query_fuzzy, [search_pattern])
    
    if not brand_id:
        return None
    
    return brand_id[0]['id']

# get id of model
async def get_model_id(brand_id: int, model: str):
    normalized_name = model.lower().strip()
    
    # First try exact match
    query_exact = """
    SELECT id FROM res_car_model WHERE car_brand_id = $1 AND lower(name) = $2
    """
    model_id = await PostgresDB.execute_query(query_exact, [brand_id, normalized_name])
    
    # If exact match not found, try fuzzy search
    if not model_id:
        # Construct the search pattern with wildcards
        search_pattern = f"%{normalized_name}%"
        query_fuzzy = """
        SELECT id FROM res_car_model WHERE car_brand_id = $1 AND lower(name) LIKE $2
        """
        model_id = await PostgresDB.execute_query(query_fuzzy, [brand_id, search_pattern])
    
    if not model_id:
        return None
    
    return model_id[0]['id']

# get id of garage
async def get_garage_id(garage_code: str):
    query = """
    select rpg.id
    from res_partner_gara rpg 
        left join res_partner rp on rp.id = rpg.partner_id
    where rp.code = $1
    limit 1
    """
    garage_id = await PostgresDB.execute_query(query, [garage_code])
    if not garage_id:
        return None
    
    return garage_id[0]['id']


# get id of province
async def get_province_id(province_code: str=None, province_name: str=None):
    # First try exact match by code
    if province_code:
        query_code = """
        SELECT id, region_id FROM res_province 
        WHERE code = $1
        """
        province = await PostgresDB.execute_query(query_code, [province_code])
        if province:
            return province[0]
    
    # Then try exact match by name
    if province_name:
        query_name = """
        SELECT id, region_id FROM res_province 
        WHERE lower(name) = $1
        """
        normalized_name = province_name.lower().strip()
        province = await PostgresDB.execute_query(query_name, [normalized_name])
        if province:
            return province[0]
    
    # Finally try fuzzy match by name
    if province_name:
        normalized_name = province_name.lower().strip()
        search_pattern = f"%{normalized_name}%"
        query_fuzzy = """
        SELECT id, region_id FROM res_province 
        WHERE lower(name) LIKE $1
        """
        province = await PostgresDB.execute_query(query_fuzzy, [search_pattern])
        if province:
            return province[0]
    
    return None

async def get_pricelist_id(garage_id: int, region_id: int):
    query = """
    SELECT id, name FROM price_list 
    WHERE active = true
    """
    params = []
    param_index = 1
    
    if garage_id:
        query += f" AND garage_id = ${param_index}"
        params.append(garage_id)
        param_index += 1
    
    if region_id:
        query += f" AND region_id = ${param_index}"
        params.append(region_id)
        
    if not garage_id and not region_id:
        return None
    
    pricelist_id = await PostgresDB.execute_query(query, params)
    if not pricelist_id:
        return None
    
    return pricelist_id[0]


async def get_item_id(item_code: str, item_name: str):
    
    item = None
    if item_code:
        query = """
        select id, code, name from insurance_claim_list_category where code = $1
        """
        item = await PostgresDB.execute_query(query, [item_code])
    
    if not item and item_name:
        query = """
        select id, code, name from insurance_claim_list_category where name = $1
        """
        item = await PostgresDB.execute_query(query, [item_name])
    
    if not item:
        return None
    
    return item[0]


async def get_item_category_id(item_code: str, item_name: str, pricelist_id: int = None):
    """
    Lấy id nhóm hạng mục từ mã hoặc tên hạng mục.
    Nếu có nhiều nhóm hạng mục và pricelist_id được cung cấp,
    thực hiện lookup để tìm item_category_id đầu tiên có giá trong bảng giá.
    
    Args:
        item_code: Mã hạng mục
        item_name: Tên hạng mục
        pricelist_id: ID của bảng giá để lookup (nếu có)
        
    Returns:
        ID của nhóm hạng mục, hoặc None nếu không tìm thấy
    """
    result = None
    
    if item_code:
        query = """
        select distinct ic.id
        from item_category ic 
        left join item_category_insurance_rel icir on ic.id = icir.item_category_id
        left join insurance_claim_list_category iclc on icir.insurance_category_id = iclc.id
        where iclc.code = $1
        """
        result = await PostgresDB.execute_query(query, [item_code])
    
    if not result and item_name:
        query = """
        select distinct ic.id
        from item_category ic 
        left join item_category_insurance_rel icir on ic.id = icir.item_category_id
        left join insurance_claim_list_category iclc on icir.insurance_category_id = iclc.id
        where iclc.name = $1
        """
        result = await PostgresDB.execute_query(query, [item_name])
    
    if not result:
        return None
    
    # Nếu không cần lookup hoặc chỉ có 1 kết quả
    if len(result) == 1 or pricelist_id is None:
        return result[0]['id']
    
    # Nếu có nhiều kết quả và có pricelist_id, thực hiện lookup
    for row in result:
        item_category_id = row['id']
        
        # Kiểm tra xem có dòng giá nào cho item_category_id này không
        check_query = """
        select count(*) as count from price_list_line 
        where pricelist_id = $1 and item_category_id = $2
        """
        check_result = await PostgresDB.execute_query(check_query, [pricelist_id, item_category_id])
        
        if check_result and check_result[0]['count'] > 0:
            # Nếu tìm thấy bản ghi trong bảng giá với item_category_id này, trả về nó
            return item_category_id
    
    # Nếu không tìm thấy item_category_id nào có trong bảng giá, trả về item_category_id đầu tiên
    return result[0]['id']


async def get_car_category_id(model_id: int, pricelist_id: int = None):
    """
    Lấy id nhóm dòng xe từ model_id.
    Nếu có nhiều nhóm dòng xe và pricelist_id được cung cấp, 
    thực hiện lookup để tìm car_category_id đầu tiên có giá trong bảng giá.
    
    Args:
        model_id: ID của model xe
        pricelist_id: ID của bảng giá để lookup (nếu có)
        
    Returns:
        ID của nhóm dòng xe, hoặc None nếu không tìm thấy
    """
    query = """
    select car_category_id from car_category_res_car_model_rel ccrcmr where res_car_model_id = $1
    """
    result = await PostgresDB.execute_query(query, [model_id])
    
    # Nếu không tìm thấy hoặc chỉ có một kết quả
    if not result:
        return None
    
    # Nếu không cần lookup hoặc chỉ có 1 kết quả
    if len(result) == 1 or pricelist_id is None:
        return result[0]['car_category_id']
    
    # Nếu có nhiều kết quả và có pricelist_id, thực hiện lookup
    for row in result:
        car_category_id = row['car_category_id']
        
        # Kiểm tra xem có dòng giá nào cho car_category_id này không
        check_query = """
        select count(*) as count from price_list_line 
        where pricelist_id = $1 and car_category_id = $2
        """
        check_result = await PostgresDB.execute_query(check_query, [pricelist_id, car_category_id])
        
        if check_result and check_result[0]['count'] > 0:
            # Nếu tìm thấy bản ghi trong bảng giá với car_category_id này, trả về nó
            return car_category_id
    
    # Nếu không tìm thấy car_category_id nào có trong bảng giá, trả về car_category_id đầu tiên
    return result[0]['car_category_id']


async def get_price(pricelist_id: int, 
                    item_id: int=None, 
                    model_id: int=None,
                    item_category_id: int=None, 
                    car_category_id: int=None, 
                    price_type: str=None):
    query = """
    select price from price_list_line pll
    where pricelist_id = $1
    """
    params = [pricelist_id]
    param_index = 2
    
    # Tạo các điều kiện dựa trên các tham số được truyền vào
    conditions = []
    
    if item_id is not None:
        conditions.append((f"item_id = ${param_index}", item_id))
        param_index += 1
        
    if model_id is not None:
        conditions.append((f"car_model_id = ${param_index}", model_id))
        param_index += 1
    
    if item_category_id is not None:
        conditions.append((f"item_category_id = ${param_index}", item_category_id))
        param_index += 1
    
    if car_category_id is not None:
        conditions.append((f"car_category_id = ${param_index}", car_category_id))
        param_index += 1
    
    if price_type is not None:
        conditions.append((f"price_type = ${param_index}", price_type))
        param_index += 1
    
    # Nếu có điều kiện, thêm vào câu truy vấn
    if conditions:
        for condition, value in conditions:
            query += f" and {condition}"
            params.append(value)
    
    # Trong trường hợp tất cả các tham số tùy chọn đều là None, chúng ta vẫn sẽ tìm kiếm theo pricelist_id
    
    query += " order by price asc limit 1"
    
    price = await PostgresDB.execute_query(query, params)
    if price and len(price) > 0:
        return price[0]['price']
    return None


@router.post("/search", response_model=AutoClaimPriceResponse)
async def search_prices(
    request: AutoClaimPriceRequest = Body(...),
    # current_user: dict = Depends(get_current_user)
):
    """
    Các bước tìm kiếm bảng giá
    1. Tìm bảng giá
        Tìm bảng giá theo garage
        Nếu không thấy, tìm bảng giá theo khu vực dựa vào tỉnh/thành phố
        Nếu không thấy, trả về kết quả rỗng
        
    2. Tìm giá chi tiết từ bảng giá
        Tìm chi tiết giá theo hiệu xe và chi tiết hạng mục chuẩn hệ thống
        
        Nếu không thấy:
            Xác định nhóm xe dựa vào hiệu xe
            Tìm chi tiết giá theo nhóm xe và hạng mục chuẩn hệ thống
            
        Nếu không thấy:
            Xác định nhóm hạng mục dựa vào hạng mục chuẩn hệ thống
            Tìm chi tiết giá dựa vào nhóm hạng mục và hiệu xe
        
        Nếu không thấy:
            Xác định nhóm hạng mục dựa vào hạng mục chuẩn hệ thống
            Xác định nhóm xe dựa vào hiệu xe
            Tìm chi tiết giá dựa vào nhóm hạng mục và nhóm xe
            
        Nếu không thấy, trả về kết quả rỗng
        
    
    Returns:
    - Thông tin giá phụ tùng
    
    {
        "pricelist": "B.1. BANG GIA SON GARA NGOAI TASCO 2024- KV HÀ NỘI",
        "price": 850000,
        "type": "paint",
        "parts": {
            "code": "CAR.1",
            "name": "Cửa trước phải"
        }
    }
    """
    
    # Tìm bảng giá đúng
    garage_id = None
    region_id = None
    # Tìm bảng giá theo garage trước
    garage_id = await get_garage_id(request.garage.code)
    pricelist = await get_pricelist_id(garage_id, region_id)
    
    # Tìm id hạng mục chuẩn hệ thống
    item = await get_item_id(request.part.code, request.part.name)
    item_id = item['id'] if item else None
    item_code = item['code'] if item else None
    item_name = item['name'] if item else None

    if not item:
        return AutoClaimPriceResponse(
            pricelist=None,
            price=None,
            parts={
                "code": item_code,
                "name": item_name
            }
        )
        
    # Nếu không tìm thấy bảng giá theo garage, tìm bảng giá theo khu vực
    if not pricelist:
        # replace garage id with None
        garage_id = None
        province = await get_province_id(request.province.code, request.province.name)
        if province:
            region_id = province['region_id']
            pricelist = await get_pricelist_id(garage_id, region_id)
    
    
    # Nếu không tìm thấy bảng giá, trả về kết quả rỗng
    if not pricelist:
        return AutoClaimPriceResponse(
            pricelist=None,
            price=None,
            parts={
                "code": item_code,
                "name": item_name
            }
        )
    
    pricelist_id = pricelist['id']
    pricelist_name = pricelist['name']
    
    # Tìm giá
    # Tìm id model
    brand_id = await get_brand_id(request.car.brand)
    model_id = await get_model_id(brand_id, request.car.model)
    
    # Tìm id nhóm dòng xe
    car_category_id = await get_car_category_id(model_id, pricelist_id)
    
    # Tìm id nhóm hạng mục chuẩn hệ thống
    item_category_id = await get_item_category_id(item_code, item_name, pricelist_id)

    # Tìm giá theo các cách khác nhau, từ chi tiết nhất đến ít chi tiết nhất
    # Cách 1: Tìm giá dựa vào pricelist_id, item_id, model_id và price_type
    price = await get_price(pricelist_id=pricelist_id, 
                           item_id=item_id, 
                           model_id=model_id, 
                           price_type=request.type)
    
    if not price and item_category_id and model_id:
        # Cách 2: Tìm giá dựa vào pricelist_id, item_category_id, model_id và price_type
        price = await get_price(pricelist_id=pricelist_id, 
                               item_category_id=item_category_id, 
                               model_id=model_id,
                               price_type=request.type)
        
    if not price and item_id and car_category_id:
        # Cách 3: Tìm giá dựa vào pricelist_id, item_id, car_category_id và price_type
        price = await get_price(pricelist_id=pricelist_id, 
                               item_id=item_id, 
                               car_category_id=car_category_id, 
                               price_type=request.type)
    
    if not price and item_category_id and car_category_id:
        # Cách 4: Tìm giá dựa vào pricelist_id, item_category_id, car_category_id và price_type
        price = await get_price(pricelist_id=pricelist_id, 
                               item_category_id=item_category_id, 
                               car_category_id=car_category_id, 
                               price_type=request.type)
        
    if not price:
        return AutoClaimPriceResponse(
            pricelist=pricelist_name,
            price=None,
            parts={
                "code": item_code,
                "name": item_name
            }
        )
    
    return AutoClaimPriceResponse(
        pricelist=pricelist_name,
        price=price,
        parts = {
            "code": item_code,
            "name": item_name
        }
    )
    
async def get_data_auto_claim_price(repair_id: int):
    query = """
    SELECT 
        repair.id, 
        rcb.name as brand, 
        rcm.name as model, 
        partner_gara.code as garage_code, 
        partner_gara.name as garage_name, 
        province.code as province_code, 
        province.name as province_name
    FROM 
        insurance_claim_solution_repair repair
        left join res_partner_gara rpg on  repair.gara_partner_id = rpg.id
        left join res_partner partner_gara on partner_gara.id = rpg.partner_id
        left join res_province province on province.id = repair.gara_province_id
        left join res_car rc on rc.id = repair.car_id
        left join res_car_brand rcb on rcb.id = rc.car_brand_id
        left join res_car_model rcm on rcm.id = rc.car_model_id
    where repair.id = $1
    limit 1
    """
    data = await PostgresDB.execute_query(query, [repair_id])
    if data:
        return data[0]
    return None
    

@router.get("/data/{repair_id}", response_model=Dict[str, Any])
async def get_data(repair_id: int,
                   current_user: dict = Depends(get_current_user)):
    data = await get_data_auto_claim_price(repair_id)
    return data