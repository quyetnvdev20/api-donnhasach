from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from ...deps import get_current_user
from typing import Optional, List
import logging
from app.schemas.auto_claim_price import AutoClaimPriceRequest, AutoClaimPriceResponse
from app.utils.erp_db import PostgresDB
router = APIRouter()
logger = logging.getLogger(__name__)

# get id of brand
async def get_brand_id(brand: str):
    normalized_name = brand.lower().strip()
    # Construct the search pattern with wildcards
    search_pattern = f"%{normalized_name}%"
    query = """
    SELECT id FROM res_car_brand WHERE lower(name) LIKE $1
    """
    brand_id = await PostgresDB.execute_query(query, [search_pattern])
    return brand_id[0]['id']

# get id of model
async def get_model_id(brand_id: int, model: str):
    normalized_name = model.lower().strip()
    # Construct the search pattern with wildcards
    search_pattern = f"%{normalized_name}%" 
    query = """
    SELECT id FROM res_car_model WHERE car_brand_id = $1 AND lower(name) LIKE $2
    """
    model_id = await PostgresDB.execute_query(query, [brand_id, search_pattern])
    return model_id[0]['id']

# get id of garage
async def get_garage_id(garage_code: str):
    query = """
    select rpg.id, rpg.gara_line
    from res_partner_gara rpg 
        left join res_partner rp on rp.id = rpg.partner_id
    where rp.code = $1
    """
    garage_id = await PostgresDB.execute_query(query, [garage_code])
    return garage_id[0]


# get id of province
async def get_province_id(province_name: str):
    # Normalize the input province name
    normalized_name = province_name.lower().strip()
    # Construct the search pattern with wildcards
    search_pattern = f"%{normalized_name}%"
    
    query = """
    SELECT id, region_id FROM res_province 
    WHERE lower(name) LIKE $1
    """
    province_id = await PostgresDB.execute_query(query, [search_pattern])
    return province_id[0]

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
    
    pricelist_id = await PostgresDB.execute_query(query, params)
    return pricelist_id[0]

async def get_item_category_id(item_category_name: str):
    query = """
    select distinct ic.id
    from item_category ic 
    left join item_category_insurance_rel icir on ic.id = icir.item_category_id
    left join insurance_claim_list_category iclc on icir.insurance_category_id = iclc.id
    where iclc.name = $1
    """
    item_category_id = await PostgresDB.execute_query(query, [item_category_name])
    return item_category_id[0]['id']

async def get_car_category_id(model_id: int):
    query = """
    select car_category_id from car_category_res_car_model_rel ccrcmr where res_car_model_id = $1
    """
    car_category_id = await PostgresDB.execute_query(query, [model_id])
    return car_category_id[0]['car_category_id']

async def get_price(pricelist_id: int, item_category_id: int, car_category_id: int, price_type: str):
    query = """
    select price from price_list_line pll
    where pricelist_id = $1
    """
    params = [pricelist_id]
    param_index = 2
    
    if item_category_id:
        query += f" and item_category_id = ${param_index}"
        params.append(item_category_id)
        param_index += 1
    
    if car_category_id:
        query += f" and car_category_id = ${param_index}"
        params.append(car_category_id)
        param_index += 1
    
    if price_type:
        query += f" and price_type = ${param_index}"
        params.append(price_type)
    
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
    1. Trường hợp là garage chính hãng -> lookup garage trong bảng giá
    2. Trường hợp là garage không phải chính hãng -> lookup tỉnh/thành phố
        2.1. Sau khi tìm thấy tỉnh/thành phố, lookup region trong bảng giá
    3. Tính toán giá
    Trường hợp garage ngoài:
        3.1. Lấy hạng mục chuẩn hệ thống -> tìm id nhóm hạng mục -> lookup id nhóm hạng mục
        3.2. Lấy hãng xe -> tìm id hãng xe
        3.3. Lấy hiệu xe + id hãng xe -> tìm id model
        3.4. Lấy id model xe -> tìm id nhóm dòng xe (lấy đầu tiên)
        3.5. Lấy id nhóm hạng mục + id nhóm dòng xe -> tìm giá
    
    Returns:
    - Thông tin giá phụ tùng
    """
    # Logic sẽ được thêm vào sau
    garage_id = None
    region_id = None
    # 1. Lấy id garage
    is_origin = request.garage.is_origin
    if is_origin:
        # Tìm id garage
        garage_id = await get_garage_id(request.garage.code)
    else:
        # Tìm id tỉnh/thành phố
        province_id = await get_province_id(request.province.name)
        region_id = province_id['region_id']
    
    # Tìm bảng giá đúng
    pricelist = await get_pricelist_id(garage_id, region_id)
    if pricelist:
        pricelist_id = pricelist['id']
        pricelist_name = pricelist['name']
    else:
        pricelist_id = None
        pricelist_name = None
    
    # Tìm giá
    # Tìm id nhóm hạng mục
    item_category_id = await get_item_category_id(request.part.name)
    
    # Tìm id model
    brand_id = await get_brand_id(request.car.brand)
    model_id = await get_model_id(brand_id, request.car.model)
    
    # Tìm id nhóm dòng xe
    car_category_id = await get_car_category_id(model_id)
    
    # Tìm giá
    price = await get_price(pricelist_id, item_category_id, car_category_id, request.type)
    
    return AutoClaimPriceResponse(
        pricelist=pricelist_name,
        price=price
    )