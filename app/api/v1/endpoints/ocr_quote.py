from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from ...deps import get_current_user
from ....config import settings, odoo
from ....database import get_db
from ....schemas.assessment import OCRQuoteResponse
import logging
import httpx
import asyncio
import json
import re
from openai import AsyncOpenAI
from ....utils.erp_db import PostgresDB
from ....utils.odoo import UserError

logger = logging.getLogger(__name__)

router = APIRouter()

with open(f'{settings.ROOT_DIR}/app/data/repair_item.json', 'r', encoding='utf-8') as f:
    LIST_REPAIR_ITEM = json.load(f)


async def get_ocr_quote_data(image_url: str):

    try:
        # Định nghĩa URL của dịch vụ OCR
        ocr_service_url = settings.OCR_SERVICE_URL

        # Lấy API key và API secret từ cấu hình
        api_key = settings.OCR_API_KEY
        api_secret = settings.OCR_API_SECRET
        
        # Tạo URL đầy đủ cho API OCR
        api_url = f"{ocr_service_url}/api/v2/ocr/document/price_quotation"
        
        # Tham số cho request
        params = {
            "img": image_url,
            "format_type": "url",
            "get_thumb": "false"
        }
        
        # Sử dụng httpx.AsyncClient với timeout dài hơn
        timeout = httpx.Timeout(90.0, connect=60.0)  # 60 giây cho toàn bộ request, 30 giây cho kết nối
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"Sending OCR request to: {api_url} with params: {params}")
            
            # Thử sử dụng Basic Auth
            response = await client.get(
                api_url,
                params=params,
                auth=(api_key, api_secret)
            )
            
            if response.status_code != 200:
                logger.error(f"OCR service returned status code {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"OCR service error: {response.text}"
                )
                
            data = response.json()
            
            return data
            
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request to OCR service timed out. Please try again later."
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error connecting to OCR service: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )
    
async def get_data_mapping():
    query = """
        SELECT DISTINCT
            line.name AS repair_item_name,
            category.id AS category_id,
            category.name AS category_name
        FROM 
            insurance_claim_solution_repair_line line
        LEFT JOIN insurance_claim_list_category category ON line.category_id = category.id
        WHERE 
        line.name IS NOT NULL 
        AND category.name IS NOT NULL
     """
     
    data_mapping = await PostgresDB.execute_query(query)
    return data_mapping


def clean_numeric_value(value):
    """
    Remove commas from numeric strings and convert to integer.
    If the value is not a string or doesn't contain commas, return it as is.
    """
    if isinstance(value, str):
        # Remove commas and convert to integer if it's a numeric string
        cleaned_value = value.replace(',', '')
        if re.match(r'^\d+$', cleaned_value):
            return int(cleaned_value)
    return value

@router.get("/ocr-quote",
            response_model=OCRQuoteResponse,
            status_code=status.HTTP_200_OK)
async def get_ocr_quote(
        image_url: str,
        current_user: dict = Depends(get_current_user)
) -> OCRQuoteResponse:
    """
    Get OCR quote from an image URL
    
    This endpoint sends the image URL to the OCR service and returns the extracted information.
    
    Parameters:
    - image_url: URL of the image to be processed
    
    Returns:
    - OCR extracted data
    """

    ocr_quote_data = await get_ocr_quote_data(image_url)
    data_mapping = {item['repair_item_name']: item for item in LIST_REPAIR_ITEM}

    # Xử lý dữ liệu OCR
    result_data = []
    item_names = []
    line_data = []
            
    if ocr_quote_data.get('data') and len(ocr_quote_data.get('data')):
        # Trước tiên, thu thập tất cả các tên hạng mục và dữ liệu tương ứng
        for item in ocr_quote_data.get('data'):
            if not item.get('info') or not item.get('info').get('table'):
                continue
                        
            table_data = item.get('info').get('table')
            if not table_data or not len(table_data):
                continue
                
            for line in table_data:
                try:
                    price = float(line.get('amount_total')) if line.get('amount_total') else 0
                    discount = float(line.get('percent_discount')) if line.get('percent_discount') else 0
                    name = line.get('description', '')
                    
                    # Thêm vào danh sách để xử lý hàng loạt
                    item_names.append(name)
                    line_data.append({
                        'name': name,
                        'price': price,
                        'discount': discount,
                        'line': line
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing line data: {line}, error: {str(e)}")
                    continue
        
        # Xử lý hàng loạt các tên hạng mục để phân loại
        if item_names:
            try:
                # Gọi API OpenAI một lần duy nhất để phân loại tất cả các hạng mục
                category_types = await process_items_batch_with_gpt(item_names)
                logger.info(f"Processed {len(category_types)} items with GPT")
                
                # Tạo kết quả cuối cùng
                for data in line_data:
                    name = data['name']
                    price = data['price']
                    discount = data['discount']
                    
                    # Lấy kết quả phân loại từ batch processing
                    category_type = category_types.get(name, {"code": "parts", "name": "Phụ tùng"})
                    
                    category = {
                        'code': None,
                        'name': None
                    }
                    if data_mapping.get(name):
                        category['code'] = clean_numeric_value(data_mapping.get(name).get('category_code'))
                        category['name'] = clean_numeric_value(data_mapping.get(name).get('category_name'))
                    
                    result_data.append({
                        'name': name,
                        'quantity': 1,
                        'garage_price': price,
                        'item': category,
                        'discount_percentage': discount,
                        'type': category_type
                    })
            except Exception as e:
                logger.error(f"Error in batch processing: {str(e)}")
                # Fallback to individual processing if batch fails

    if not result_data or not len(result_data):
        raise UserError("Không tìm thấy dữ liệu")   
            
    return OCRQuoteResponse(
        url_cvs=image_url,
        data=result_data
    )

async def process_items_batch_with_gpt(item_names: List[str]) -> Dict[str, dict]:
    """
    Process multiple items in a single call to OpenAI
    
    Args:
        item_names: List of item names to classify
        
    Returns:
        Dictionary mapping item names to their category types
    """
    if not item_names:
        return {}
    
    # Chuẩn bị prompt cho xử lý hàng loạt
    items_text = "\n".join([f"{i+1}. {name}" for i, name in enumerate(item_names)])
    
    prompt = f"""Bạn sẽ được cung cấp danh sách các tên tổn thất của xe ô tô.
Bạn cần mapping mỗi tên với 1 trong 3 phương án xử lý là: 1.Sơn, 2.Phụ tùng, 3.Nhân công.

Bạn hãy tham khảo những rule sau:
1. Có chữ Sơn ở đầu: Tính là Sơn
2. Có những hành động thể hiện việc sửa chữa như công, Gò, Đồng, Nhân công, Sửa, Tháo lắp, Phục hồi, Gia công, Tháo, Hàn, Khắc phục, Vỗ móp (thiên về 1 hành động) ở đầu: Tính là Nhân công
3. Còn lại sẽ là Phụ tùng

Danh sách các tên tổn thất:
{items_text}

Trả ra output dạng JSON với key là tên tổn thất và value là object có dạng {{'code': Mã phương án, 'name': Tên phương án}}
Trả ra output dạng json: {{'code': Mã phương án, 'name': Tên phương án, 'color_code': Mã màu}}
1. code của phương án sơn là paint, name là Sơn, color_code là #531dab  
2. code của phương án phụ tùng là parts, name là Phụ tùng, color_code là #0958d9
3. code của phương án nhân công là labor, name là Nhân công, color_code là #d46b08
"""
    
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Bạn là trợ lý phân loại tổn thất xe ô tô."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        response_content = response.choices[0].message.content
        result = json.loads(response_content)
        
        # Đảm bảo kết quả trả về đúng định dạng
        processed_result = {}
        for name, category in result.items():
            if isinstance(category, dict) and 'code' in category and 'name' in category:
                processed_result[name] = category
            else:
                # Fallback nếu định dạng không đúng
                processed_result[name] = {"code": "parts", "name": "Phụ tùng"}
        
        return processed_result
    except Exception as e:
        logger.error(f"Error in batch processing with GPT: {str(e)}")
        # Trả về dictionary rỗng trong trường hợp lỗi
        return {name: {"code": "parts", "name": "Phụ tùng"} for name in item_names}

async def process_item_with_gpt(item_name: str) -> dict:
    # try:
    prompt = f"""Bạn sẽ được cung cấp tên tổn thất của 1 chiếc xe ô tô.
Bạn cần mapping nó với 1 trong 3 phương án xử lý là : 1.Sơn, 2.Phụ tùng, 3.Nhân công.
Bạn hãy tham khảo những rule sau:
1. Có chữ Sơn ở đầu: Tính là Sơn
2. Có những hành động thể hiện việc sửa chữa như công, Gò,Đồng, Nhân công, Sửa, Tháo lắp, Phục hồi, Gia công, Tháo, Hàn, Khắc phục , Vỗ móp (thiên về 1 hành động) ở đầu: Tính là Nhân công
3. Còn lại sẽ là Phụ tùng
Trả ra output dạng json: {{'code': Mã phương án, 'name': Tên phương án}}
1. code của phương án sơn là paint, name là Sơn
2. code của phương án phụ tùng là parts, name là Phụ tùng
3. code của phương án nhân công là labor, name là Nhân công
"""
    
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "developer", "content": prompt},
            {
                "role": "user",
                "content": item_name
            }
        ],
        response_format={"type": "json_object"}
    )
    response_content = response.choices[0].message.content
    output = json.loads(response_content)
    return output

    # except Exception as e:
    #     raise e
