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
from ....utils.erp_db import PostgresDB

logger = logging.getLogger(__name__)

router = APIRouter()


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
        timeout = httpx.Timeout(60.0, connect=30.0)  # 60 giây cho toàn bộ request, 30 giây cho kết nối
        
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
            logger.info(f"OCR response received: {data}")
            
            # Xử lý dữ liệu OCR
            result_data = []
            
            if data.get('data') and len(data.get('data')):
                for item in data.get('data'):
                    if not item.get('info') or not item.get('info').get('table'):
                        continue
                        
                    table_data = item.get('info').get('table')
                    if not table_data or not len(table_data):
                        continue
                        
                    for line in table_data:
                        try:
                            price = float(line.get('amount_total')) if line.get('amount_total') else 0
                            discount = float(line.get('percent_discount')) if line.get('percent_discount') else 0
                            
                            result_data.append({
                                'name': line.get('description', ''),
                                'quantity': 1,
                                'price_unit_gara': price,
                                'category_id': 1540,
                                'discount': discount,
                            })
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error parsing line data: {line}, error: {str(e)}")
                            continue
            
            return OCRQuoteResponse(
                url_cvs=image_url,
                data=result_data
            )
            
    except httpx.TimeoutException as e:
        logger.error(f"Request to OCR service timed out: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request to OCR service timed out. Please try again later."
        )
    except httpx.RequestError as e:
        logger.error(f"Error connecting to OCR service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error connecting to OCR service: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error processing OCR request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )
       