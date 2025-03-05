from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from ....database import get_db
from ...deps import get_current_user
from ....schemas.assessment import AssessmentListItem, VehicleDetailAssessment, AssessmentDetail, DocumentCollection, \
    DocumentResponse, DocumentUpload, DocumentType, UpdateAssessmentItemResponse
from ....utils.erp_db import PostgresDB
import json
import httpx
import logging
from app.config import settings, odoo

router = APIRouter()
logger = logging.getLogger(__name__)

color = {
    'wait': '#2196F3',
    'done': '#4CAF50',
    'cancel': '#212121',
}

@router.get("/document_type")
async def get_document_type(
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get document type information
    """
    logger.info(f"current_user: {current_user}")
    # Get document type from odoo
    query = """
        SELECT 
            id,
            name,
            type_document,
            description
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
            "description": doc_type["description"] or ""
        })
    
    return result

@router.get("", response_model=List[AssessmentListItem])
async def get_assessment_list(
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get list of assessments that need to be processed
    """
    query = f"""
        SELECT
            gd_chi_tiet.id AS id,
            rc.license_plate AS license_plate,
            rcb.name AS vehicle,
            gd_chi_tiet.name_driver AS customer_name,
            gd_chi_tiet.name AS name,
            gd_chi_tiet.state AS status,
            CONCAT_WS(', ', 
                NULLIF(first_damage.location_damage, ''),
                NULLIF(ward.name, ''),
                NULLIF(district.name, ''),
                NULLIF(province.name, '')
            ) AS assessment_address,
            TO_CHAR(icr.date_damage, 'DD/MM/YYYY - HH24:MI') AS notification_time,
            TO_CHAR(icr.date_damage + INTERVAL '3 hours', 'DD/MM/YYYY - HH24:MI') AS complete_time,
            icr.note AS note
        FROM insurance_claim_appraisal_detail gd_chi_tiet
        LEFT JOIN insurance_claim_receive icr ON icr.id = gd_chi_tiet.insur_claim_id
        LEFT JOIN res_car rc ON rc.id = gd_chi_tiet.car_id
        LEFT JOIN res_car_brand rcb ON rcb.id = rc.car_brand_id
        LEFT JOIN LATERAL (
            SELECT * FROM insurance_claim_damage icd 
            WHERE icd.insur_claim_id = icr.id
            ORDER BY icd.id
            LIMIT 1
        ) AS first_damage ON true
        LEFT JOIN res_province province ON province.id = first_damage.province_id
        LEFT JOIN res_district district ON district.id = first_damage.district_id
        LEFT JOIN res_ward ward ON ward.id = first_damage.ward_id
        WHERE 1=1
    """

    params = []

    if search:
        query += """
            AND (
                gd_chi_tiet.name ILIKE $1
                OR rc.license_plate ILIKE $1
                OR rcb.name ILIKE $1
                OR gd_chi_tiet.name_driver ILIKE $1
                OR CONCAT_WS(', ', 
                    NULLIF(first_damage.location_damage, ''),
                    NULLIF(ward.name, ''),
                    NULLIF(district.name, ''),
                    NULLIF(province.name, '')
                ) ILIKE $1
            )
        """
        params.append(f"%{search}%")

    # Add ordering and pagination
    query += f"""
    ORDER BY gd_chi_tiet.id DESC
    LIMIT {limit} OFFSET {offset}
    """

    results = await PostgresDB.execute_query(query, params)

    # Add status_color based on status
    enhanced_results = []
    for result in results:
        # Convert result to dict if it's not already
        if not isinstance(result, dict):
            result = dict(result)

        # Add status_color based on the status
        status = result.get('status')
        result['status_color'] = color.get(status, '#757575')  # Default to gray if status not found

        # Add random values for current_distance and assessment_progress
        result['urgency_level'] = True
        result['current_distance'] = 2.5
        result['assessment_progress'] = 1

        enhanced_results.append(result)

    return enhanced_results


@router.get("/{assessment_id}", response_model=AssessmentDetail)
async def get_assessment_detail(
        assessment_id: str,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get detailed information about a specific assessment
    """
    query = f"""
            SELECT
                gd_chi_tiet.name AS case_number,
                rc.license_plate AS license_plate,
                rcb.name AS vehicle,
                CONCAT_WS(', ', 
                    NULLIF(first_damage.location_damage, ''),
                    NULLIF(ward.name, ''),
                    NULLIF(district.name, ''),
                    NULLIF(province.name, '')
                ) AS location,
                gd_chi_tiet.name_driver AS owner_name,
                gd_chi_tiet.phone_driver AS phone_number,
                gd_chi_tiet.state AS status,
                icr.description_damage AS incident_desc,
                icr.sequel_damage AS damage_desc,
                TO_CHAR(icr.date_damage, 'DD/MM/YYYY - HH24:MI') AS accident_date,
                TO_CHAR(gd_chi_tiet.date, 'DD/MM/YYYY - HH24:MI') AS appraisal_date,
                TO_CHAR(icr.date_damage + INTERVAL '3 hours', 'DD/MM/YYYY - HH24:MI') AS complete_time,
                icr.note AS note
            FROM insurance_claim_appraisal_detail gd_chi_tiet
            LEFT JOIN insurance_claim_receive icr ON icr.id = gd_chi_tiet.insur_claim_id
            LEFT JOIN res_car rc ON rc.id = gd_chi_tiet.car_id
            LEFT JOIN res_car_brand rcb ON rcb.id = rc.car_brand_id
            LEFT JOIN LATERAL (
                SELECT * FROM insurance_claim_damage icd 
                WHERE icd.insur_claim_id = icr.id
                ORDER BY icd.id
                LIMIT 1
            ) AS first_damage ON true
            LEFT JOIN res_province province ON province.id = first_damage.province_id
            LEFT JOIN res_district district ON district.id = first_damage.district_id
            LEFT JOIN res_ward ward ON ward.id = first_damage.ward_id
            WHERE gd_chi_tiet.id = $1
        """

    params = [int(assessment_id)]

    assessment_detail = await PostgresDB.execute_query(query, params)
    if assessment_detail:
        assessment_detail = assessment_detail[0]
        assessment_detail['assessment_progress'] = 100
        assessment_detail['status_color'] = color.get(assessment_detail['status'], '#757575')  # Default to gray if status not found
        assessment_detail['tasks'] = [{
            "seq": 1,
            "name": "Giám định chi tiết xe",
            "path": "/detail",
            "desc": "Kiểm tra trực tiếp các hạng mục và mực độ tổn thất",
            "icon": "https://example.com",
            "status": {
                "bg_color": "#00000",
                "name": "completed",
            }
        },
            {
                "seq": 2,
                "name": "Thu thập hồ sơ",
                "path": "/collect_document",
                "desc": "Chụp và trích xuất thông tin từ giấy tờ cần thiết",
                "icon": "https://example.com",
                "status": {
                    "bg_color": "#00000",
                    "name": "completed",
                }
            },
            {
                "seq": 3,
                "name": "Upload Thông tin tai nạn & Yêu cầu BT",
                "path": "/accident_notification",
                "desc": "Chia sẻ, in và upload bản kí tươi",
                "icon": "https://example.com",
                "status": {
                    "bg_color": "#00000",
                    "name": "completed",
                }
            },
            {
                "seq": 4,
                "name": "Upload Biên bản giám định & Xác định thiệt hại",
                "path": "/assessment_report",
                "desc": "Chia sẻ, in và upload bản kí tươi",
                "icon": "https://example.com",
                "status": {
                    "bg_color": "#00000",
                    "name": "completed",
                }
            }
        ]
    else:
        assessment_detail = None
    return assessment_detail


@router.get("/{assessment_id}/detail", response_model=VehicleDetailAssessment)
async def get_vehicle_detail_assessment(
        assessment_id: str,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get detailed vehicle assessment information
    """

    # Query to fetch assessment categories with their details
    query = f"""
        SELECT 
            ica.id,
            ica.category_id, 
            iclc.name as category_name,
            ica.status,
            isc.name as status_name,
            ica.solution as solution_code,
            to_char(ica.date, 'dd/mm/YYYY') as date           
            from insurance_claim_attachment_category ica
        left join insurance_type_document itd on ica.type_document_id = itd.id
        left join insurance_state_category isc on ica.status = isc.id
        left join insurance_claim_list_category iclc on ica.category_id = iclc.id
        where detail_category_id = {assessment_id}
    """

    # Execute the query and get results
    results = await PostgresDB.execute_query(query)
    assessment_detail = []
    if results:
        # Process each assessment category item
        for item in results:
            item_id = item.get('id')

            # Query to fetch images related to this category
            sql_image = f"""
                SELECT 
                    ica.id,
                    ica.link_preview as link,
                    ica.location,
                    ica.lat,
                    ica.long,
                    to_char(ica.date_upload, 'dd/mm/YYYY hh:mm:ss') as date_upload
                FROM insurance_claim_attachment ica
                WHERE ica.category_id = {item_id}
            """
            # Execute image query and get results
            result_image = await PostgresDB.execute_query(sql_image)
            list_image = []

            # Process each image for this category
            if result_image:
                for res in result_image:
                    list_image.append({
                        'id': res.get('id'),
                        'link': res.get('link'),
                        'location': res.get('location'),
                        'lat': res.get('lat'),
                        'long': res.get('long'),
                        'date': res.get('date_upload'),
                    })

            # Build the assessment detail object with category info and images
            assessment_detail.append({
                'id': item_id,
                'category_id': {
                    'id': item.get('category_id'),
                    'name': item.get('category_name'),
                },
                'status': {
                    'id': item.get('status'),
                    'name': item.get('status_name'),
                },
                'solution': {
                    'code': item.get('solution_code'),
                    'name': 'Sửa chữa' if item.get('solution_code') == 'repair' else (
                        'Thay thế' if item.get('solution_code') == 'replace' else '')
                },
                'images': list_image
            })

    return {
        "assessment_id": int(assessment_id),
        "items": assessment_detail
    }


@router.put("/{assessment_id}/detail", response_model=UpdateAssessmentItemResponse)
async def update_vehicle_detail_assessment(
        assessment_id: str,
        vehicle_detail: VehicleDetailAssessment,
        current_user: dict = Depends(get_current_user)
):

    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    """
    Update vehicle detail assessment information
    """
    vals_items = []

    for item in vehicle_detail.items:
        val_images = []
        for image in item.images:
            val_images.append({
                'id': image.id,
                'link': image.link,
                'location': image.location,
                'lat': image.lat,
                'long': image.long,
                'date_upload': image.date
            })

        vals_items.append({
            'id': item.id,
            'category_id': item.category_id.id,
            'listImageRemove': item.listImageRemove,
            'status': item.status.id,
            'solution': item.solution.code,
            'images': val_images
        })

    body = {
        'assessment_id': int(assessment_id),
        'items': vals_items
    }

    response = await odoo.call_method_not_record(
        model='insurance.claim.appraisal.detail',
        method='update_insurance_assessment_detail',
        token=settings.ODOO_TOKEN,
        kwargs=body
    )

    if response:
        return UpdateAssessmentItemResponse(assessment_id=assessment_id, status="Success")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update accident notification")


@router.post("/{assessment_id}/done")
async def done_assessment(
        assessment_id: str,
        current_user: dict = Depends(get_current_user)
):
    """
    Done assessment
    """
    return {
        "id": assessment_id,
        "status": "Success"
    }

#Xóa các danh mục ảnh hạng mục giám định
@router.delete("/{claim_attachment_category_id}")
async def delete_claim_attachment_category(
        claim_attachment_category_id: str,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Delete claim attachment category
    """
    try:
        # Validate user authentication
        if not current_user.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )

        # Call Odoo to delete the claim attachment category
        response = await odoo.delete_method(
            model='insurance.claim.attachment.category',
            record_id=claim_attachment_category_id,
            token=settings.ODOO_TOKEN
        )

        if response:
            return {
                "id": claim_attachment_category_id,
                "status": "Success"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete claim attachment category"
            )
    except Exception as e:
        logger.error(f"Error deleting claim attachment category: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete claim attachment category: {str(e)}"
        )
