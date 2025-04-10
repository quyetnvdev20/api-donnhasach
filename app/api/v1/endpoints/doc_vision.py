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
    if  not request.list_image_url or not request.list_image_url[0]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image not found."
        )

    image_url = request.list_image_url[0]

    document_type = await get_document_type()
    json_document_type = {doc["name"]: doc["code"] for doc in document_type}
    json_document_id = {doc["code"]: doc["id"] for doc in document_type}

    # Wait for image to be available, with timeout
    max_retries = 3
    retry_delay = 1  # seconds
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries):
            try:
                image = await client.get(image_url)
                if image.status_code == 200 and image.content:
                    base64_image = base64.b64encode(image.content).decode('utf-8')
                    break
                await asyncio.sleep(retry_delay)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Image URL is not accessible after maximum retries"
                    )
                await asyncio.sleep(retry_delay)

    ocr_image_results = await process_image_with_gpt(base64_image, json_document_type, json_document_id)
    
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
    try:
        content_dict = json.loads(ocr_image_results)
        doc_type = content_dict.get("code")
        side = content_dict.get("side")

        if doc_type == "driving_license" and side == 'front':
            content_details = await get_ocr_license(base64_image, 'gplx')
            response["gplx_no"] = content_details.get("number")
            response["name_driver"] = content_details.get("name")
            response["gplx_level"] = content_details.get("class_")
            response["gplx_effect_date"] = content_details.get("date")
            response["gplx_expired_date"] = content_details.get("expried_date")

        elif doc_type == "vehicle_registration" and side == 'front':
            content_details = await get_ocr_license(base64_image, 'dk')
            month = f"0{content_details.get('month')}" if len(content_details.get('month')) == 1 else content_details.get('month')
            registry_date = f"{content_details.get('day')}/{month}/{content_details.get('year')}"
            response["registry_no"] = content_details.get("seri")
            response["registry_date"] = registry_date
            response["registry_expired_date"] = content_details.get("expired_date")

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


async def process_image_with_gpt(base64_image, document_type: dict, document_id: dict):
    try:
        prompt = f"""Ảnh sau là một loại giấy tờ xe tại Việt Nam. Hãy giúp tôi:

        1. Xác định đây là loại tài liệu nào trong các loại sau:
           - "driving_license": Giấy phép lái xe
           - "vehicle_registration_photo": Giấy đăng ký xe (cà-vẹt xe)
           - "vehicle_registration": Giấy chứng nhận kiểm định (giấy đăng kiểm)
           - "insurance_certificate": Giấy chứng nhận bảo hiểm
           
        2. Xác định mặt giấy tờ là:
            - `"front"` nếu là mặt chứa thông tin chính như:
              - Ảnh chân dung, họ tên, số giấy phép (đối với GPLX)
              - Thông tin kỹ thuật xe, dấu đỏ, số sê-ri (đối với đăng kiểm)
              - Thông tin chủ xe, biển số, số khung, màu sơn... (đối với đăng ký xe)
            - `"back"` nếu là mặt còn lại, thường chứa:
              - Điều khoản (đối với bảo hiểm)
              - Lịch kiểm định (đối với đăng kiểm)
              - Các hạng bằng còn lại (đối với GPLX)

        3. Nếu nhận diện được, hãy trích xuất dữ liệu theo định dạng JSON dưới đây:

        {{
          "code": "<code từ danh sách trên>",
          "id": "<id tương ứng từ document_id>",
          "name": "<tên đầy đủ loại tài liệu>",
          "side": "<front | back>",
        }}

        4. Nếu không xác định được loại giấy tờ, trả về JSON rỗng: {{}}
        
        5. Nếu mặt giấy tờ là "back":
           - Vẫn phải trả về đầy đủ các trường: "code", "id", "name", "side"

        **Yêu cầu:** Chỉ trả về JSON object đúng định dạng. Không đưa ra bất kỳ giải thích, mô tả hay nội dung dư thừa nào.

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
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Error processing image with GPT: {str(e)}")
        raise e


async def get_ocr_license(base64_image, document_type):
    url = f"{settings.OCR_LICENSE_URL}/{document_type}"
    payload = {
        "image_base64": base64_image,
    }
    headers = {
        'accept': 'application/json',
        'x-api-key': settings.OCR_LICENSE_API_KEY,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                data=payload,
                timeout=10.0
            )

            if response.status_code != 200:
                return {}

            response_data = response.json()
            logger.info(f"get_driven_license.cccd_ocr.response={response_data}")

            if len(response_data) > 0:
                data = response_data.get('data', {})
                return data

            return {}
    except Exception as e:
        logger.error(f"Error in get_driven_license: {str(e)}")
        return {}

