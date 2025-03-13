import base64
import os
import json

from fastapi import APIRouter, Depends, HTTPException, status, Body
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from typing import List, Optional
from ....database import get_db
from ...deps import get_current_user
from ....schemas.doc_vision import DocVisionRequest, DocVisionResponse
import logging
import httpx
from .assessment import get_document_type
from ....utils.erp_db import PostgresDB
from ....config import settings


router = APIRouter()
logger = logging.getLogger(__name__)
    
@router.post('/', response_model=DocVisionResponse)
async def doc_vision(request: DocVisionRequest, current_user: dict = Depends(get_current_user)):
    document_type = await get_document_type()
    json_document_type = {doc["name"]: doc["code"] for doc in document_type}
    json_document_id = {doc["code"]: doc["id"] for doc in document_type}
    response = await process_image_with_gpt(request.image_url, json_document_type, json_document_id)
    # Create a response that matches the DocVisionResponse schema
    response_dict = json.loads(response)
    formatted_response = {
        "type": response_dict.get("code", {}),
        "name": response_dict.get("name", {}),
        "type_document_id": response_dict.get("id", {}),
        "content": response_dict.get("content", {}),
        "image_url": request.image_url
    }
    
    return formatted_response

async def get_document_type():
    # Get document type from odoo
    query = """
        SELECT 
            id,
            name,
            type_document
        FROM insurance_type_document
        WHERE active IS TRUE
        ORDER BY priority_level
        LIMIT 100
    """

    document_types = await PostgresDB.execute_query(query)
    result = []

    for doc_type in document_types:
        result.append({
            "id": doc_type["id"],
            "name": doc_type["name"],
            "code": doc_type["type_document"] or "",
        })

    return result


async def process_image_with_gpt(image_url: str, document_type: dict, document_id: dict):
    try:
        print(document_type)
        async with httpx.AsyncClient() as client:
            image = await client.get(image_url)
            base64_image = base64.b64encode(image.content).decode('utf-8')
        
        prompt = f"""Bạn là một chuyên gia nhận diện các loại tài liệu cá nhân của người dân Việt Nam.
Hãy nhận diện loại tài liệu cá nhân trong hình ảnh sau đây.
Tài liệu cá nhân có thể là, lấy dữ liệu từ danh sách bên dưới:
{document_type}
{document_id}

Nếu loại tài liệu là "Giấy phép lái xe" thì đọc thêm dữ liệu trong ảnh được mô tả như sau:
birth_date: ngày sinh
class_: Hạng/Class
date: ngày cấp
expired_date: ngày hết hạn
name: tên chủ giấy phép lái xe
number: số giấy phép lái xe

Nếu loại tài liệu là "Đăng kiểm xe" thì đọc thêm dữ liệu trong ảnh được mô tả như sau:
registration_number: số đăng kiểm
registration_date: ngày đăng kiểm
registration_expired_date: ngày hết hạn

**Output yêu cầu:**
- Trả về dữ liệu dưới dạng JSON 1 object.
- JSON bao gồm: code của tài liệu, id của tài liệu cá nhân và name của tài liệu cá nhân. ID để dạng string.
- Nếu thuộc 2 loại Giấy phép lái xe và Đăng kiểm xe thì thêm trường content vào JSON.
- Không trả ra bất kỳ thông tin nào khác.
"""
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    except Exception as e:
        raise e
