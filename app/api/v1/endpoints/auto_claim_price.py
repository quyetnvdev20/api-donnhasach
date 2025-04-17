from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from ...deps import get_current_user
from typing import Optional, List
import logging
from app.schemas.auto_claim_price import AutoClaimPriceRequest, AutoClaimPriceResponse
from app.utils.erp_db import PostgresDB
from app.utils.odoo import UserError
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
    if not brand_id:
        return None
    
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
async def get_province_id(province_name: str):
    # Normalize the input province name
    normalized_name = province_name.lower().strip()
    # Construct the search pattern with wildcards
    search_pattern = f"%{normalized_name}%"
    
    query = """
    SELECT id, region_id FROM res_province 
    WHERE lower(name) LIKE $1
    """
    province = await PostgresDB.execute_query(query, [search_pattern])
    if not province:
        return None
    
    return province[0]

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


async def get_item_category_id(item_code: str, item_name: str):
    if item_code:
        query = """
        select distinct ic.id
        from item_category ic 
        left join item_category_insurance_rel icir on ic.id = icir.item_category_id
        left join insurance_claim_list_category iclc on icir.insurance_category_id = iclc.id
        where iclc.code = $1
        """
        item_category_id = await PostgresDB.execute_query(query, [item_code])
        if not item_category_id:
            return None
        
        return item_category_id[0]['id']
    
    if item_name:
        query = """
        select distinct ic.id
        from item_category ic 
        left join item_category_insurance_rel icir on ic.id = icir.item_category_id
        left join insurance_claim_list_category iclc on icir.insurance_category_id = iclc.id
        where iclc.name = $1
        """
        item_category_id = await PostgresDB.execute_query(query, [item_name])
        if not item_category_id:
            return None
        
        return item_category_id[0]['id']
    
    return None


async def get_car_category_id(model_id: int):
    query = """
    select car_category_id from car_category_res_car_model_rel ccrcmr where res_car_model_id = $1
    """
    car_category_id = await PostgresDB.execute_query(query, [model_id])
    if not car_category_id:
        return None
    
    return car_category_id[0]['car_category_id']


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
    
    if item_id:
        query += f" and item_id = ${param_index}"
        params.append(item_id)
        param_index += 1
        
    if model_id:
        query += f" and car_model_id = ${param_index}"
        params.append(model_id)
        param_index += 1
    
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
        "pricelist": "B.1. BANG GIA SON GARA NGOAI TASCO 2024- KV HÀ NỘI",
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
        province = await get_province_id(request.province.name)
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
    car_category_id = await get_car_category_id(model_id)
    
    # Tìm id nhóm hạng mục chuẩn hệ thống
    item_category_id = await get_item_category_id(item_code, item_name)

    # Tìm price từ bảng giá
    price = await get_price(pricelist_id=pricelist_id, 
                            item_id=item_id, 
                            model_id=model_id, 
                            price_type=request.type)
    
    if not price:
        # Tìm giá dựa vào nhóm hạng mục chuẩn hệ thống và hiệu xe
        price = await get_price(pricelist_id=pricelist_id, 
                                item_category_id=item_category_id, 
                                model_id=model_id,
                                price_type=request.type)
        
    if not price:
        # Tìm giá dựa vào hạng mục chuẩn hệ thống và nhóm dòng xe
        price = await get_price(pricelist_id=pricelist_id, 
                                item_id=item_id, 
                                car_category_id=car_category_id, 
                                price_type=request.type)
    
    if not price:
        # Tìm giá dựa vào nhóm hạng mục chuẩn hệ thống và nhóm dòng xe
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