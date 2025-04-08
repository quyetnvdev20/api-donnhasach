import base64
import os
import json
import asyncio
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
    
@router.post('', response_model=DocVisionResponse)
async def doc_vision(request: DocVisionRequest, current_user: dict = Depends(get_current_user)):
    document_type = await get_document_type()
    json_document_type = {doc["name"]: doc["code"] for doc in document_type}
    json_document_id = {doc["code"]: doc["id"] for doc in document_type}
    ocr_image_tasks = [process_image_with_gpt(image_url, json_document_type, json_document_id) for image_url in request.list_image_url]
    ocr_image_results = await asyncio.gather(*ocr_image_tasks)
    
    # Khởi tạo response theo cấu trúc DocVisionResponse
    response = {
        "name_driver": None,
        "gplx_no": None,
        "gplx_level": None,
        "gplx_effect_date": None,
        "gplx_expired_date": None,
        "registry_no": None,
        "registry_date": None,
        "registry_expired_date": None,
        "documents": []
    }
    
    # Dictionary để gom các ảnh theo loại tài liệu
    grouped_documents = {}
    
    # Phân loại và xử lý kết quả từ các ảnh
    for result in ocr_image_results:
        for image_url, content in result.items():
            try:
                content_dict = json.loads(content)
                doc_type = content_dict.get("code")
                
                if not doc_type:
                    continue
                
                # Cập nhật thông tin chi tiết theo loại giấy tờ
                content_details = content_dict.get("content", {})
                
                if doc_type == "driving_license" and content_details:
                    response["gplx_no"] = content_details.get("number")
                    response["name_driver"] = content_details.get("name")
                    response["gplx_level"] = content_details.get("class_")
                    response["gplx_effect_date"] = content_details.get("date")
                    response["gplx_expired_date"] = content_details.get("expired_date")
                
                elif doc_type == "vehicle_registration":
                    response["registry_no"] = content_details.get("serial_number")
                    response["registry_date"] = content_details.get("registry_date")
                    response["registry_expired_date"] = content_details.get("registry_expired_date")
                
                # Gom các ảnh theo loại tài liệu
                if doc_type not in grouped_documents:
                    grouped_documents[doc_type] = {
                        "type": doc_type,
                        "type_document_id": content_dict.get("id"),
                        "name": content_dict.get("name"),
                        "images": [{
                            "date": None,
                            "description": None,
                            "id": None,
                            "lat": None,
                            "long": None,
                            "location": None,
                            "link": image_url
                        }]
                    }
                else:
                    # Thêm ảnh vào danh sách ảnh của loại tài liệu này
                    grouped_documents[doc_type]["images"].append({
                        "date": None,
                        "description": None,
                        "id": None,
                        "lat": None,
                        "long": None,
                        "location": None,
                        "link": image_url
                    })
                
            except Exception as e:
                logger.error(f"Error processing result for image {image_url}: {str(e)}")
    
    # Thêm các document đã gom ảnh vào response
    response["documents"] = list(grouped_documents.values())
    
    return response


async def get_document_type():
    # Get document type from odoo
    query = """
        SELECT 
            id,
            name,
            type_document
        FROM insurance_type_document
        WHERE active IS TRUE
        AND type_document in ('driving_license', 'vehicle_registration', 'insurance_certificate', 'vehicle_registration_photo')
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
        async with httpx.AsyncClient() as client:
            image = await client.get(image_url)
            base64_image = base64.b64encode(image.content).decode('utf-8')

        prompt = f"""Ảnh sau là một loại giấy tờ xe tại Việt Nam. Hãy giúp tôi:

        1. Xác định đây là loại tài liệu nào trong các loại sau:
           - "driving_license": Giấy phép lái xe
           - "vehicle_registration_photo": Giấy đăng ký xe (cà-vẹt xe)
           - "vehicle_registration": Giấy chứng nhận kiểm định (giấy đăng kiểm)
           - "insurance_certificate": Giấy chứng nhận bảo hiểm

        2. Nếu nhận diện được, hãy trích xuất dữ liệu theo định dạng JSON dưới đây:

        {{
          "code": "<code từ danh sách trên>",
          "id": "<id tương ứng từ document_id>",
          "name": "<tên đầy đủ loại tài liệu>",
        }}

        - Nếu là "driving_license", content bao gồm:
          - name: tên người lái
          - number: số GPLX
          - class_: hạng bằng
          - date: ngày cấp (DD/MM/YYYY)
          - expired_date: ngày hết hạn (DD/MM/YYYY)
          - birth_date: ngày sinh (DD/MM/YYYY)

        - Nếu là "vehicle_registration_photo", content bao gồm:
          - owner: tên chủ xe
          - plate_number: biển số
          - brand: nhãn hiệu xe
          - engine_number: số máy
          - chassis_number: số khung
          - color: màu sơn
          - registration_date: ngày đăng ký (DD/MM/YYYY)
          - registration_expired_date: ngày hết hạn (nếu có) (DD/MM/YYYY)

        - Nếu là "vehicle_registration", content bao gồm:
          - inspection_number: số đăng kiểm
          - registry_date: ngày cấp đăng kiểm (DD/MM/YYYY)
          - registry_expired_date: Có hiệu lực đến ngày (valid until), Gần dấu đỏ, cạnh lề trái, dưới cả phần chữ ký và con dấu (DD/MM/YYYY)
          - vehicle_type: loại xe
          - brand: nhãn hiệu
          - engine_number: số máy
          - chassis_number: số khung
          - fuel_type: nhiên liệu
          - weight: khối lượng
          - seat_number: số chỗ ngồi
          - serial_number: số của phôi giấy chứng nhận, giá trị sau cụm từ **"Số sê-ri: (No.)"**, thường có dạng "DB-XXXXXXX"

        3. Nếu không xác định được loại giấy tờ, trả về JSON rỗng: {{}}

        **Yêu cầu:** Chỉ trả về JSON object đúng định dạng. Không đưa ra bất kỳ giải thích, mô tả hay nội dung dư thừa nào, Đảm bảo định dạng ngày tháng theo mẫu.

        document_type = {document_type}
        document_id = {document_id}"""

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là một chuyên gia OCR và hiểu rõ các loại giấy tờ xe tại Việt Nam."
                },
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
        return {image_url: response.choices[0].message.content}

    except Exception as e:
        logger.error(f"Error processing image with GPT: {str(e)}")
        raise e
    
