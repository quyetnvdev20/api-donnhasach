from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from ....database import get_db
from ...deps import get_current_user
from ....schemas.assessment import AssessmentListItem, VehicleDetailAssessment, AssessmentDetail, DocumentCollection, \
    DocumentResponse, DocumentUpload, DocumentType, UpdateAssessmentItemResponse
from .assessment import get_document_type
from ....utils.erp_db import PostgresDB
import json
import httpx
import logging
import asyncio
from app.config import settings, odoo

router = APIRouter()
logger = logging.getLogger(__name__)



async def get_data_collect_document(assessment_id: int):
    sql_query = """
        select 
            icad.id as id,
            icad.state as state,
            icad.name_driver as name_driver,
            icad.phone_driver as phone_driver,
            icad.gender_driver as gender_driver,
            icad.cccd_driver as cccd_driver,
            icad.gplx_no as gplx_no,
            icad.gplx_level as gplx_level,
            icad.gplx_effect_date as gplx_effect_date,
            icad.gplx_expired_date as gplx_expired_date,
            icad.is_add_request as is_add_request,
            icad.registry_no as registry_no,
            icad.registry_date as registry_date,
            icad.registry_expired_date as registry_expired_date,
            icad.user_id as user_id,
            icad.state_assign as state_assign,
            icr.appraisal_ho_id as appraisal_ho_id,
            icad.object as object   
             from insurance_claim_appraisal_detail icad
            join insurance_claim_receive icr on icad.insur_claim_id = icr.id
            where icad.id = $1
    """
    result = await PostgresDB.execute_query(sql_query, (assessment_id,))
    return result[0]

async def get_image_document(assessment_id: int):
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
                   to_char(ica.date_upload + INTERVAL '7 hours', 'dd/mm/YYYY hh:mm:ss') as date_upload
                 from insurance_claim_attachment_category icac
                     left join insurance_type_document itc on icac.type_document_id = itc.id
                     left join insurance_claim_attachment ica on icac.id = ica.category_id        
        where itc.active = true
        and icac.detail_profile_attachment_id = $1
    """
    result = await PostgresDB.execute_query(sql_query, (assessment_id,))
    return result


async def format_image_document(document_type, image_document):
    dic_image = {}
    list_image = []
    for document_type in document_type:
        dic_image.update({
            document_type.get('id'): {
                'name': document_type.get('name'),
                'type_document_id': document_type.get('id'),
                'desc': document_type.get('description'),
                'type': document_type.get('code'),
                'images': [],
            }
        })


    if image_document:
        for i in image_document:
            if not i.get('type_document_id') or not dic_image.get(i.get('type_document_id')) or not i.get('link'):
                continue
            dic_image[i.get('type_document_id')]['images'].append({
                'thumbnail': 'https://file-cdn.baohiemtasco.vn/insurance-data/car-video-thumb.jpeg',
                'id': i.get('id'),
                'description': i.get('itc_description'),
                'link': i.get('link'),
                'location': i.get('location'),
                'lat': i.get('lat'),
                'long': i.get('long'),
                'date': i.get('date_upload'),
            })

    for image in dic_image:
        list_image.append(dic_image.get(image))

    return list_image

@router.get("/{assessment_id}/collect_document")
async def get_document_collection(
        assessment_id: int,
        current_user: dict = Depends(get_current_user)
):
    
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    """
    Get document collection information
    """

    ocr_data, image_document, document_type = await asyncio.gather(
        get_data_collect_document(assessment_id),
        get_image_document(assessment_id),
        get_document_type()
    )

    list_image = await format_image_document(document_type, image_document)

    data = {
        'name_driver': ocr_data.get('name_driver'),
        'phone_driver': ocr_data.get('phone_driver'),
        'cccd': ocr_data.get('cccd_driver'),
        'gender_driver': ocr_data.get('gender_driver'),
        'gplx_effect_date': ocr_data.get('gplx_effect_date'),
        'gplx_expired_date': ocr_data.get('gplx_expired_date'),
        'gplx_level': ocr_data.get('gplx_level'),
        'gplx_no': ocr_data.get('gplx_no'),
        'registry_date': ocr_data.get('registry_date'),
        'registry_expired_date': ocr_data.get('registry_expired_date'),
        'registry_no': ocr_data.get('registry_no'),
        'documents': list_image
    }

    return data


@router.put("/{assessment_id}/collect_document", response_model=DocumentCollection)
async def update_document_collection(
        assessment_id: str,
        document_collection: DocumentCollection,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Update document collection information
    """
    # In a real implementation, you would save the data to the database
    # For now, we'll just return the input data
    return document_collection