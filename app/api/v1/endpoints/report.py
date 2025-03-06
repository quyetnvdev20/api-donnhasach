from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from ....config import settings, odoo
from ....database import get_db
from ...deps import get_current_user, api_key_header
from ....schemas.assessment import DocumentResponse, DocumentUpload, UpdateDocumentResponse
from ....utils.erp_db import PostgresDB
from ....utils.odoo import Odoo
from ....utils.redis_client import redis_client
import httpx
import asyncio
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Khởi tạo đối tượng Odoo với config
config = {
    'ODOO_URL': settings.ODOO_URL,
    'ODOO_TOKEN': settings.ODOO_TOKEN
}
odoo = Odoo(config=config)

async def get_receive_id(assessment_id: int):
    sql_query = """
        select insur_claim_id
        from insurance_claim_appraisal_detail icad 
        where id = $1
    """
    result = await PostgresDB.execute_query(sql_query, (assessment_id,))
    return result[0]['insur_claim_id']

async def get_image_list(assessment_id: int, document_type: str):
    sql_query = """
        select ica.id,
                   icac.name,
                   ica.link_preview as link,
                   icac.type_document_id,
                   to_char(icac.date, 'dd/mm/YYYY') as date,
                   itc.type_document,
                   itc.name                         as itc_name,
                   itc.description                  as itc_description,
                   ica.location,
                   ica.lat,
                   ica.long,
                   to_char(ica.date_upload + INTERVAL '7 hours', 'dd/mm/YYYY hh:mm:ss') as date_upload,
                   receive_id
                 from insurance_claim_attachment_category icac
                     left join insurance_type_document itc on icac.type_document_id = itc.id
                     left join insurance_claim_attachment ica on icac.id = ica.category_id        
        where 1=1
        and itc.type_document = $1
        and icac.detail_profile_attachment_id = $2
    """
    result = await PostgresDB.execute_query(sql_query, (document_type, assessment_id))
    return result

async def get_id_document_type(document_type: str):
    sql_query = """
        select id, type_document
        from insurance_type_document 
        where type_document = $1
    """
    result = await PostgresDB.execute_query(sql_query, (document_type,))
    return result[0]['id']

async def get_report_url(report_name: str, id: str, authorization: str):
    # TODO: Cần refactor lại, hàm này call về api insurance -> refactor call orm odoo
    request_body = {
        "data": [
            f"/report/pdf/{report_name}/{id}",
            "qweb-pdf"
        ]
    }
    header = {
        "Authorization": authorization
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{settings.INSURANCE_API_URL}/claim/report/{id}", json=request_body, headers=header)
        if response.status_code == 200:
            url = response.json().get("data")
            if await is_url_valid(url):
                return url
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get report")

async def format_build_body(assessment_id: int, document_upload: DocumentUpload, document_type: str):
    scan_urls = []
    for url in document_upload.scan_url:
        if hasattr(url, 'dict'):  # Nếu là Pydantic model
            scan_urls.append(url.dict())
        elif hasattr(url, '__dict__'):  # Nếu là object khác
            scan_urls.append(vars(url))
        else:  # Nếu là kiểu dữ liệu cơ bản
            scan_urls.append(str(url))
            
    id_document_type = await get_id_document_type(document_type)
    body = {
        "id": assessment_id,
        "profile_attachment_ids":
            {
                "image" : [
                    {
                        "type_document_id": id_document_type,
                        "type": document_type,
                        "list_image": scan_urls
                    }
                ],
                "listImageRemove": document_upload.list_image_remove
            }
    }
    return body

async def is_url_valid(url: str) -> bool:
    """
    Kiểm tra URL có khả dụng không
    """
    if not url:
        return False
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.head(url, timeout=2, follow_redirects=True)
            return response.status_code < 400
    except Exception as e:
        logger.error(f"Error checking URL validity: {e}")
        return False

@router.get("/{assessment_id}/accident_notification", response_model=DocumentResponse)
async def get_accident_notification(
        assessment_id: int,
        current_user: dict = Depends(get_current_user)
):
    """
    Get accident notification report
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Tạo cache key cho preview URL
    cache_key = f"accident_notification_preview:{assessment_id}"
    
    # Thử lấy preview URL từ Redis
    cached_preview_url, list_image = await asyncio.gather(redis_client.get(cache_key), get_image_list(assessment_id, "accident_ycbt"))
    
    # Kiểm tra URL trong cache có khả dụng không
    if cached_preview_url and await is_url_valid(cached_preview_url):
        logger.info(f"Using cached preview URL for assessment_id: {assessment_id}")
        return {
            "preview_url": cached_preview_url,
            "scan_url": list_image
        }
    
    # Nếu không có trong cache hoặc URL không khả dụng, lấy từ API
    # Get receive_id from assessment_id
    receive_id = await get_receive_id(assessment_id)
    if not receive_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    
    # Get accident notification template from config
    accident_notification_template = settings.ACCIDENT_NOTIFICATION_TEMPLATE
    accident_notification_url = await get_report_url(accident_notification_template, receive_id, current_user.get('access_token'))
    
    # Kiểm tra URL mới có khả dụng không trước khi lưu vào Redis
    if accident_notification_url and await is_url_valid(accident_notification_url):
        # Lưu vào Redis không có thời gian timeout (expiry=None)
        await redis_client.set(cache_key, accident_notification_url, expiry=None)
        logger.info(f"Cached preview URL for assessment_id: {assessment_id}")
    else:
        logger.warning(f"Generated URL is not valid for assessment_id: {assessment_id}")
        
    return {
        "preview_url": accident_notification_url or "",
        "scan_url": list_image
    }

@router.post("/{assessment_id}/accident_notification/refresh", response_model=DocumentResponse)
async def refresh_accident_notification_url(
        assessment_id: int,
        current_user: dict = Depends(get_current_user)
):
    """
    Refresh accident notification preview URL
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Tạo cache key cho preview URL
    cache_key = f"accident_notification_preview:{assessment_id}"
    
    # Xóa cache hiện tại nếu có
    await redis_client.delete(cache_key)
    logger.info(f"Deleted cached preview URL for assessment_id: {assessment_id}")
    
    # Get receive_id from assessment_id
    receive_id = await get_receive_id(assessment_id)
    if not receive_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receive ID not found")
    
    # Get accident notification template from config
    accident_notification_template = settings.ACCIDENT_NOTIFICATION_TEMPLATE
    accident_notification_url = await get_report_url(accident_notification_template, receive_id, current_user.get('access_token'))
    
    # Lấy danh sách hình ảnh
    image_list = await get_image_list(assessment_id, "accident_ycbt")
    
    # Kiểm tra URL mới có khả dụng không trước khi lưu vào Redis
    if accident_notification_url and await is_url_valid(accident_notification_url):
        # Lưu vào Redis không có thời gian timeout (expiry=None)
        await redis_client.set(cache_key, accident_notification_url, expiry=None)
        logger.info(f"Cached new preview URL for assessment_id: {assessment_id}")
    else:
        logger.warning(f"Generated URL is not valid for assessment_id: {assessment_id}")
    
    return {
        "preview_url": accident_notification_url or "",
        "scan_url": image_list
    }

@router.put("/{assessment_id}/accident_notification", response_model=UpdateDocumentResponse)
async def update_accident_notification(
        assessment_id: int,
        document_upload: DocumentUpload,
        current_user: dict = Depends(get_current_user)
):
    """
    Update accident notification information
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Prepare body
    body = await format_build_body(assessment_id, document_upload, 'accident_ycbt')
    # Update accident notification
    # TODO: Kế thừa lại hàm cũ từ core erp, cần refactor
    response = await odoo.call_method_not_record(
        model='insurance.claim.appraisal.detail',
        method='update_profile_attachment',
        token=settings.ODOO_TOKEN,
        kwargs=body
    )
    
    if response:
        return UpdateDocumentResponse(status="Success")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update accident notification")

@router.get("/{assessment_id}/assessment_report", response_model=DocumentResponse)
async def get_assessment_report(
        assessment_id: int,
        current_user: dict = Depends(get_current_user)
):
    """
    Get assessment report information
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Tạo cache key cho preview URL
    cache_key = f"assessment_report_preview:{assessment_id}"
    
    # Thử lấy preview URL từ Redis và danh sách hình ảnh cùng lúc
    cached_preview_url, image_list = await asyncio.gather(
        redis_client.get(cache_key), 
        get_image_list(assessment_id, "assessment_report")
    )
    
    # Kiểm tra URL trong cache có khả dụng không
    if cached_preview_url and await is_url_valid(cached_preview_url):
        logger.info(f"Using cached preview URL for assessment report, assessment_id: {assessment_id}")
        return {
            "preview_url": cached_preview_url,
            "scan_url": image_list
        }
    
    # Nếu không có trong cache hoặc URL không khả dụng, lấy từ API
    # Get receive_id from assessment_id
    receive_id = await get_receive_id(assessment_id)
    if not receive_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    
    # Get assessment report template from config
    assessment_report_template = settings.ASSESSMENT_REPORT_TEMPLATE
    assessment_report_url = await get_report_url(assessment_report_template, assessment_id,
                                                     current_user.get('access_token'))
    
    # Kiểm tra URL mới có khả dụng không trước khi lưu vào Redis
    if assessment_report_url and await is_url_valid(assessment_report_url):
        # Lưu vào Redis không có thời gian timeout (expiry=None)
        await redis_client.set(cache_key, assessment_report_url, expiry=None)
        logger.info(f"Cached preview URL for assessment report, assessment_id: {assessment_id}")
    else:
        logger.warning(f"Generated URL is not valid for assessment report, assessment_id: {assessment_id}")
    
    return {
        "preview_url": assessment_report_url or "",
        "scan_url": image_list
    }

@router.put("/{assessment_id}/assessment_report", response_model=UpdateDocumentResponse)
async def update_assessment_report(
        assessment_id: int,
        document_upload: DocumentUpload,
        current_user: dict = Depends(get_current_user)
):
    """
    Update assessment report information
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    body = await format_build_body(assessment_id, document_upload, 'appraisal_report')
    # TODO: Kế thừa lại hàm cũ từ core erp, cần refactor
    response = await odoo.call_method_not_record(
        model='insurance.claim.appraisal.detail',
        method='update_profile_attachment',
        token=settings.ODOO_TOKEN,
        kwargs=body
    )
    
    if response:
        return UpdateDocumentResponse(status="Success")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update assessment report")

@router.post("/{assessment_id}/assessment_report/refresh", response_model=DocumentResponse)
async def refresh_assessment_report_url(
        assessment_id: int,
        current_user: dict = Depends(get_current_user)
):
    """
    Refresh assessment report preview URL
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Tạo cache key cho preview URL
    cache_key = f"assessment_report_preview:{assessment_id}"
    
    # Xóa cache hiện tại nếu có
    await redis_client.delete(cache_key)
    logger.info(f"Deleted cached preview URL for assessment_id: {assessment_id}")
    
    # Get assessment report template from config
    assessment_report_template = settings.ASSESSMENT_REPORT_TEMPLATE
    assessment_report_url = await get_report_url(assessment_report_template, assessment_id,
                                                     current_user.get('access_token'))
    
    # Lấy danh sách hình ảnh
    image_list = await get_image_list(assessment_id, "assessment_report")
    
    # Kiểm tra URL mới có khả dụng không trước khi lưu vào Redis
    if assessment_report_url and await is_url_valid(assessment_report_url):
        # Lưu vào Redis không có thời gian timeout (expiry=None)
        await redis_client.set(cache_key, assessment_report_url, expiry=None)
        logger.info(f"Cached new preview URL for assessment report, assessment_id: {assessment_id}")
    else:
        logger.warning(f"Generated URL is not valid for assessment report, assessment_id: {assessment_id}")
    
    return {
        "preview_url": assessment_report_url or "",
        "scan_url": image_list
    }
