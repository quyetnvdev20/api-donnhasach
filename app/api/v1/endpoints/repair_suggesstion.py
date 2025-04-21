from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json
from ...deps import get_current_user
from ....config import settings, odoo
from ....database import get_db
from ....schemas.repair import RepairPlanApprovalRequest, RepairPlanApprovalResponse, RepairPlanListResponse, \
    RepairPlanDetailResponse, RepairPlanApproveRequest, RepairPlanApproveResponse, RepairPlanRejectRequest, \
    RepairPlanRejectResponse, RepairCategory, RejectionReason
import logging
import asyncio
import json
from ....utils.erp_db import PostgresDB
from ..endpoints.auto_claim_price import search_prices
from ....schemas.auto_claim_price import AutoClaimPriceRequest, CarObject, PartObject, GarageObject, ProvinceObject
logger = logging.getLogger(__name__)

router = APIRouter()


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


async def get_line_id(repair_id: int):
    query = """
    select 
	line.id,
    case
        when line.price_paint_propose is not null then 'paint'
        when line.price_replace_propose is not null then 'parts'
        when line.price_labor_propose is not null then 'labor'
        else null
    end as type,
    iclc.code as category_code,
    iclc.name as category_name
    from insurance_claim_solution_repair_line line
    left join insurance_claim_list_category iclc on line.category_id = iclc.id
    where line.solution_repair_id = $1
    """
    data = await PostgresDB.execute_query(query, [repair_id])
    if data:
        return data  # Trả về tất cả các dòng, không chỉ dòng đầu tiên
    return []  # Trả về list rỗng thay vì None


async def get_suggestion_price_with_repair(repair_id: int):

    data_auto_claim_price, lines = await asyncio.gather(
        get_data_auto_claim_price(repair_id),
        get_line_id(repair_id)
    )

    # Lấy dữ liệu từ bảng insurance_claim_solution_repair
    brand = data_auto_claim_price.get('brand') if data_auto_claim_price else None
    model = data_auto_claim_price.get('model') if data_auto_claim_price else None
    province_code = data_auto_claim_price.get('province_code') if data_auto_claim_price else None
    province_name = data_auto_claim_price.get('province_name') if data_auto_claim_price else None
    garage_code = data_auto_claim_price.get('garage_code') if data_auto_claim_price else None
    garage_name = data_auto_claim_price.get('garage_name') if data_auto_claim_price else None

    # Đảm bảo lines là một list
    if not lines:
        return []

    # Gọi api dữ liệu từ kho giá auto_claim_price

    for line in lines:
        try:
            if isinstance(line, str):
                logger.error(f"Line is a string, not a dictionary: {line}")
                continue

            category_code = line.get('category_code', None)
            category_name = line.get('category_name', None)
            category_type = line.get('type', None)

            logger.warning(f"category_code: {category_code}, brand: {brand}, model: {model}")

            if not category_code or not brand or not model:
                logger.warning(f"Missing required data for item: {category_name}")
                line['suggestion_price'] = 0
                continue

            # Tạo đối tượng AutoClaimPriceRequest thay vì dict
            price_request = AutoClaimPriceRequest(
                car=CarObject(brand=brand, model=model),
                part=PartObject(code=category_code, name=category_name),
                type=category_type,
                province=ProvinceObject(code=province_code or "", name=province_name or ""),
                garage=GarageObject(code=garage_code or "", name=garage_name or "")
            )

            # Gọi hàm search_prices với đối tượng AutoClaimPriceRequest
            price_response = await search_prices(price_request)

            # Lấy giá từ response và cập nhật vào item
            if price_response is None:
                line['suggestion_price'] = 0
            elif hasattr(price_response, 'price') and price_response.price is not None:
                line['suggestion_price'] = price_response.price
            else:
                line['suggestion_price'] = 0

        except Exception as e:
            logger.error(f"Error getting suggestion price for item: {str(e)}")
            line['suggestion_price'] = 0
            continue

    return lines

async def get_and_update_repair_line(repair_id: int):
    # update multiple record
    lines = await get_suggestion_price_with_repair(repair_id)
    
    if not lines:
        logger.warning(f"No lines found for repair_id {repair_id}")
        return {"line_ids": []}
        
    vals = {
        'line_ids': [(1, line['id'], {'suggestion_price': line['suggestion_price']}) for line in lines]
    }
    
    logger.info(f"Updating repair lines with values: {vals}")
    response = await odoo.update_method(
        model='insurance.claim.solution.repair',
        record_id=repair_id,
        vals=vals
    )
    if response:
        return True
    return False
    
    