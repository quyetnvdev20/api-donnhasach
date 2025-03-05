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
import httpx
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

async def get_report_url(report_name: str, id: str, authorization: str):
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
        print(response)
        if response.status_code == 200:
            return response.json().get("data")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get report")



@router.get("/{assessment_id}/accident_notification", response_model=DocumentResponse)
async def get_accident_notification(
        assessment_id: int,
        current_user: dict = Depends(get_current_user)
):
    """
    Get accident notification information
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Get receive_id from database
    receive_id = await get_receive_id(assessment_id)
    if not receive_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receive ID not found")
    
    # Get accident notification template from config
    accident_notification_template = settings.ACCIDENT_NOTIFICATION_TEMPLATE
    accident_notification_url = await get_report_url(accident_notification_template, receive_id, current_user.get('access_token'))
    
    image_list = await get_image_list(assessment_id, "accident_ycbt")

    return {
        "preview_url": accident_notification_url,
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
    # Chuyển đổi các đối tượng không thể serialize thành JSON
    scan_urls = []
    for url in document_upload.scan_url:
        if hasattr(url, 'dict'):  # Nếu là Pydantic model
            scan_urls.append(url.dict())
        elif hasattr(url, '__dict__'):  # Nếu là object khác
            scan_urls.append(vars(url))
        else:  # Nếu là kiểu dữ liệu cơ bản
            scan_urls.append(str(url))
    
    body = {
        "id": assessment_id,
        "profile_attachment_ids":
            {
                "image" : [
                    {
                        "type_document_id": document_upload.type_document_id,
                        "type": document_upload.type,
                        "list_image": scan_urls  # Sử dụng danh sách đã được xử lý
                    }
                ],
                "listImageRemove": document_upload.list_image_remove
            }

    }
    
    # In a real implementation, you would save the data to the database
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

    # Mock data for now - in production this would come from a database
    assessment_report = {
        "id": 1,
        "preview_url": "",
        "scan_url": [
            {
                "date": "27/02/2025 11:02:09",
                "description": "",
                "id": 117348,
                "lat": "21.004388702201652",
                "link": "https://dev-storage.baohiemtasco.vn/forum.carpla.online/tic-store/1740672577458314_9_1740672577398258_compressed_image_1740672577263_claim.png",
                "location": "Q. Thanh Xuân, Thành Phố Hà Nội, Việt Nam",
                "long": "105.80242028756557",
            },
            {
                "date": "27/02/2025 11:02:09",
                "description": "",
                "id": 117348,
                "lat": "21.004388702201652",
                "link": "https://dev-storage.baohiemtasco.vn/forum.carpla.online/tic-store/1740672577458314_9_1740672577398258_compressed_image_1740672577263_claim.png",
                "location": "Q. Thanh Xuân, Thành Phố Hà Nội, Việt Nam",
                "long": "105.80242028756557",
            }
        ]
    }

    return assessment_report


@router.put("/{assessment_id}/assessment_report", response_model=DocumentResponse)
async def update_assessment_report(
        assessment_id: str,
        document_upload: DocumentUpload,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Update assessment report information
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # In a real implementation, you would save the data to the database
    # For now, we'll create a mock response
    response = {
        "id": 1,
        "preview_url": "",
        "scan_url": document_upload.scan_url
    }

    return response