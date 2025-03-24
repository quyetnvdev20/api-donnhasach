from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Annotated
from pydantic import BaseModel
from ....utils.erp_db import PostgresDB
import logging
from app.config import settings, odoo

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_assessment_detail_status(assessment_id: int) -> Dict[str, Any]:
    """
    Check if assessment has category documents and return status.
    
    Args:
        assessment_id: The ID of the assessment to check
        
    Returns:
        Dictionary with status information
    """
    query = """
        SELECT EXISTS (
            SELECT 1
            FROM insurance_claim_attachment att
            JOIN insurance_claim_attachment_category cat ON att.category_id = cat.id
            where cat.detail_category_id = $1
        ) AS has_category_documents;
    """
    res = await PostgresDB.execute_query(query, (assessment_id,))
    has_documents = res[0].get('has_category_documents', False)
    
    if has_documents:
        return {"name": "completed"}
    else:
        return {"name": "in_progress"}


async def get_collection_document_status(assessment_id: int) -> Dict[str, Any]:
    """
    Check if assessment has both driving license and vehicle registration documents.
    
    Args:
        assessment_id: The ID of the assessment to check
        
    Returns:
        Dictionary with status information
    """
    query = """
        SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1
            FROM insurance_claim_attachment att
            JOIN insurance_claim_attachment_category cat ON att.category_id = cat.id
            JOIN insurance_type_document doc ON cat.type_document_id = doc.id
            WHERE cat.detail_profile_attachment_id = $1
                AND doc.type_document IN ('driving_license', 'vehicle_registration')
            GROUP BY cat.detail_profile_attachment_id
            HAVING COUNT(DISTINCT doc.type_document) = 2
        ) THEN TRUE
        ELSE FALSE
    END AS has_collection_documents; 
    """
    res = await PostgresDB.execute_query(query, (assessment_id,))
    has_documents = res[0].get('has_collection_documents', False)
    
    if has_documents:
        return {"name": "completed"}
    else:
        return {"name": "in_progress"}


async def get_accident_notification_status(assessment_id: int) -> Dict[str, Any]:
    """
    Check if assessment has accident notification documents.
    
    Args:
        assessment_id: The ID of the assessment to check
        
    Returns:
        Dictionary with status information
    """
    query = """
        SELECT EXISTS (
            SELECT 1
            FROM insurance_claim_attachment att
            JOIN insurance_claim_attachment_category cat ON att.category_id = cat.id
            JOIN insurance_type_document doc ON cat.type_document_id = doc.id
            WHERE doc.type_document = 'accident_ycbt'
            and cat.detail_profile_attachment_id = $1
        ) AS has_accident_ycbt_documents;
    """
    res = await PostgresDB.execute_query(query, (assessment_id,))
    has_documents = res[0].get('has_accident_ycbt_documents', False)
    
    if has_documents:
        return {"name": "completed"}
    else:
        return {"name": "in_progress"}

async def get_user_request_remote_inspection(assessment_id: int, invitation_code: str) -> Dict[str, Any]:
    if not invitation_code:
        return {}
    query = """
        select 
            'Người yêu cầu giám định từ xa' as label,
            c.name,
            to_char(a.create_date + INTERVAL '7 hours','dd/MM/yyyy HH24:MI') as datetime_request
        
        from insurance_claim_remote_inspection a
        inner join res_users b on a.create_uid = b.id
        inner join res_partner c on b.partner_id = c.id
        where a.appraisal_detail_id = $1
        and a.invitation_code = $2
        limit 1
    """
    result = await PostgresDB.execute_query(query, (assessment_id, invitation_code))
    if result and result[0]:
        return result[0]
    return {}


async def get_remote_inspection(assessment_id: int, invitation_code: str) -> List[Dict[str, Any]]:
    if invitation_code:
        return []
    query = """
        select 
        id,
        name,
        phone,
        invitation_code,
        status
        
    from insurance_claim_remote_inspection
    where appraisal_detail_id = $1
    """
    result = await PostgresDB.execute_query(query, (assessment_id,))
    data = []
    for res in result:
        if res.get('status') == 'new':
            label = "Đang chờ giám định từ xa"
            message = f"Hồ sơ này đang chờ người khác thực hiện giám định từ xa với mã: {res.get('invitation_code')}"
            btn_cancel = True
            btn_share = True
        else:
            label = "Đã hoàn thành giám định từ xa"
            message = f"Hồ sơ này đã được giám định từ xa bởi: {res.get('name')}"
            btn_cancel = False
            btn_share = False
        vals = {
            'id': res.get('id'),
            'name': res.get('name'),
            'phone': res.get('phone'),
            'invitation_code': res.get('invitation_code'),
            'status': res.get('status'),
            'label': label,
            'message': message,
            'btn_cancel': btn_cancel,
            'btn_share': btn_share,
        }
        data.append(vals)
    return data

async def get_assessment_report_status(assessment_id: int) -> Dict[str, Any]:
    """
    Check if assessment has assessment report documents.
    
    Args:
        assessment_id: The ID of the assessment to check
        
    Returns:
        Dictionary with status information
    """
    query = """
        SELECT EXISTS (
            SELECT 1
            FROM insurance_claim_attachment att
            JOIN insurance_claim_attachment_category cat ON att.category_id = cat.id
            JOIN insurance_type_document doc ON cat.type_document_id = doc.id
            WHERE doc.type_document = 'appraisal_report'
            and cat.detail_profile_attachment_id = $1
        ) AS has_assessment_report_documents;
    """
    res = await PostgresDB.execute_query(query, (assessment_id,))
    has_documents = res[0].get('has_assessment_report_documents', False)
    
    if has_documents:
        return {"name": "completed"}
    else:
        return {"name": "in_progress"}