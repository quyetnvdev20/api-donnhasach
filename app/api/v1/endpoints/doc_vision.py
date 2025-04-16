import asyncio
import base64
import json
import logging
from io import BytesIO
import time

import httpx
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, status
from openai import AsyncOpenAI

from .assessment import get_document_type
from ...deps import get_current_user
from ....config import settings
from ....schemas.doc_vision import DocVisionRequest, DocVisionResponse
from ....utils.erp_db import PostgresDB

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

    first_start_time = time.perf_counter()
    logger.info(f"===============Start time took seconds")

    document_type = await get_document_type()
    json_document_type = {doc["name"]: doc["code"] for doc in document_type}
    json_document_id = {doc["code"]: doc["id"] for doc in document_type}

    start_time = time.perf_counter()
    base64_original, base64_resized = await fetch_and_resize_image_with_retry(image_url)
    fetch_time = time.perf_counter() - start_time
    logger.info(f"fetch_and_resize_image_with_retry took {fetch_time:.2f} seconds")

    start_time = time.perf_counter()
    ocr_image_results = await process_image_with_gpt(base64_resized, json_document_type, json_document_id)
    gpt_time = time.perf_counter() - start_time
    logger.info(f"process_image_with_gpt took {gpt_time:.2f} seconds")
    
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
            start_time = time.perf_counter()
            content_details = await get_ocr_license(base64_original, 'gplx')
            ocr_time = time.perf_counter() - start_time
            logger.info(f"get_ocr_license (gplx) took {ocr_time:.2f} seconds")
            if content_details:
                response["gplx_no"] = content_details.get("number")
                response["name_driver"] = content_details.get("name")
                response["gplx_level"] = content_details.get("class_")
                response["gplx_effect_date"] = content_details.get("date")
                response["gplx_expired_date"] = content_details.get("expried_date")

        elif doc_type == "vehicle_registration" and side == 'front':
            start_time = time.perf_counter()
            content_details = await get_ocr_license(base64_original, 'dk')
            ocr_time = time.perf_counter() - start_time
            logger.info(f"get_ocr_license (dk) took {ocr_time:.2f} seconds")
            if content_details:
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

    end_fetch_time = time.perf_counter() - first_start_time
    logger.info(f"===============End time took {end_fetch_time:.2f} seconds")
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


async def fetch_and_resize_image_with_retry(image_url: str, max_size: tuple = (800, 800), retries: int = 3,
                                            delay: int = 1):
    """
    Tải ảnh từ image_url, thử lại nếu chưa có sẵn, sau đó resize về kích thước max_size và trả về base64.
    """
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                if response.status_code == 200 and response.content:
                    image_bytes = response.content
                    # Ảnh gốc
                    base64_original = base64.b64encode(image_bytes).decode("utf-8")

                    # Resize ảnh bằng Pillow
                    image = Image.open(BytesIO(image_bytes))
                    # Chuyển đổi sang RGB nếu ảnh ở chế độ RGBA
                    if image.mode == 'RGBA':
                        image = image.convert('RGB')
                    image.thumbnail(max_size, Image.ANTIALIAS)

                    buffer = BytesIO()
                    image.save(buffer, format="JPEG", quality=90)
                    base64_resized = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    return base64_original, base64_resized
        except Exception as e:
            if attempt == retries - 1:
                raise RuntimeError(f"Không thể tải ảnh sau {retries} lần thử: {e}")

        await asyncio.sleep(delay)

    raise RuntimeError("Ảnh không khả dụng sau khi retry.")


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
             - Thông tin kỹ thuật xe, dấu đỏ, số sê-ri, hình ảnh phương tiện (đối với đăng kiểm)
             - Tên chủ xe, biển số, màu sơn, nhãn hiệu, số khung, số máy (đối với giấy đăng ký xe)
           - `"back"` nếu là mặt còn lại, thường chứa:
             - Điều khoản, hướng dẫn sử dụng, bảng kiểm (đối với bảo hiểm hoặc đăng kiểm)
             - Các hạng bằng còn lại (đối với GPLX)

        3. Gợi ý phân biệt:
           - Nếu là **giấy đăng ký xe (vehicle_registration_photo)**: có thông tin chủ xe, màu sơn, biển số xe, ngày đăng ký lần đầu, thường không có thông tin kỹ thuật hoặc ảnh xe.
           - Nếu là **giấy đăng kiểm (vehicle_registration)**: có bảng "THÔNG SỐ KỸ THUẬT", số sê-ri (No.), dấu mộc đỏ, ảnh xe, và đôi khi có dòng "CÓ HIỆU LỰC ĐẾN".

        4. Nếu nhận diện được, hãy trích xuất dữ liệu theo định dạng JSON dưới đây:

        {{
          "code": "<code từ danh sách trên>",
          "id": "<id tương ứng từ document_id>",
          "name": "<tên đầy đủ loại tài liệu>",
          "side": "<front | back>"
        }}

        5. Nếu không xác định được loại giấy tờ, trả về JSON rỗng: {{}}

        6. Nếu mặt giấy tờ là "back":
           - Vẫn phải trả về đầy đủ các trường: "code", "id", "name", "side"

        **Yêu cầu:** Chỉ trả về JSON object đúng định dạng. Không đưa ra bất kỳ giải thích, mô tả hay nội dung dư thừa nào.

        document_type = {document_type}
        document_id = {document_id}
        """
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o-2024-11-20",
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
                timeout=20.0
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

