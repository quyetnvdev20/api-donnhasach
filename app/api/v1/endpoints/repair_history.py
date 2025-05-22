from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json
from ...deps import get_current_user
from ....config import settings, odoo
from ....database import get_db
from ....schemas.repair_history import RepairHistoryRequest,RepairHistoryResponse
import logging
import asyncio
import json
from ....utils.erp_db import PostgresDB
from datetime import datetime
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/",
             response_model=RepairHistoryResponse,
             status_code=status.HTTP_200_OK)
async def create_repair_history(
        request: RepairHistoryRequest,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
) -> RepairHistoryResponse:
    query = '''
    select cp.id from  car_profile cp join res_car rc on cp.car_id = rc.id
        where rc.vin = '{}'
    '''.format(request.vin)

    data = await PostgresDB.execute_query(query)
    if data:
        for item in data:
            insert_query = '''
            INSERT INTO repair_history (
                car_profile_id, amount_total, amount_subtotal, 
                amount_tax_total, repair_date, repair_type
            ) VALUES (
                $1, $2, $3, $4, $5, $6
            ) RETURNING id;
            '''
            values = (
                item.get('id'),  # car_profile_id từ kết quả query trước
                request.amount_total,
                request.amount_subtotal,
                request.amount_tax_total,
                datetime.strptime(request.repair_date, '%Y-%m-%d %H:%M:%S'),  # Đã là datetime object từ validator
                request.repair_type
            )
            result = await PostgresDB.execute_query(insert_query, values)
            return RepairHistoryResponse(id=result[0][0])

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Không tìm thấy thông tin xe với VIN này"
    )