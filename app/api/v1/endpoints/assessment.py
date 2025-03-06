from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Annotated
from pydantic import BaseModel
from datetime import datetime
from ....database import get_db
from ...deps import get_current_user
from ....schemas.assessment import AssessmentListItem, VehicleDetailAssessment, AssessmentDetail, DocumentCollection, \
    DocumentResponse, DocumentUpload, DocumentType, UpdateAssessmentItemResponse
from ....schemas.common import CommonHeaders
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
        headers: Annotated[CommonHeaders, Header()],
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user),
):
    """
    Get list of assessments that need to be processed
    """
    time_zone = headers.time_zone
    query = f"""
        SELECT
            gd_chi_tiet.id AS id,
            rc.license_plate AS license_plate,
            rcb.name AS vehicle,
            contact.name AS customer_name,
            gd_chi_tiet.name AS name,
            gd_chi_tiet.state AS status,
            CONCAT_WS(', ', 
                NULLIF(icr.location_damage, ''),
                NULLIF(ward.name, ''),
                NULLIF(district.name, ''),
                NULLIF(province.name, '')
            ) AS location,
            rpg.display_name AS assessment_address,
            TO_CHAR(icr.date_damage AT TIME ZONE 'UTC' AT TIME ZONE $1, 'DD/MM/YYYY - HH24:MI') AS notification_time,
            TO_CHAR((icr.date_damage + INTERVAL '3 hours') AT TIME ZONE 'UTC' AT TIME ZONE $1, 'DD/MM/YYYY - HH24:MI') AS complete_time,
            icr.note AS note
        FROM insurance_claim_appraisal_detail gd_chi_tiet
        LEFT JOIN insurance_claim_receive icr ON icr.id = gd_chi_tiet.insur_claim_id
        LEFT JOIN res_partner_gara rpg ON rpg.id = gd_chi_tiet.gara_partner_id
        LEFT JOIN res_partner contact ON contact.id = icr.person_contact_id
        LEFT JOIN res_car rc ON rc.id = gd_chi_tiet.car_id
        LEFT JOIN res_car_brand rcb ON rcb.id = rc.car_brand_id
--         LEFT JOIN LATERAL (
--             SELECT * FROM insurance_claim_damage icd 
--             WHERE icd.insur_claim_id = icr.id
--             ORDER BY icd.id
--             LIMIT 1
--         ) AS first_damage ON true
--         LEFT JOIN LATERAL (
--             SELECT * FROM insurance_contract_certification icc 
--             LEFT JOIN insurance_claim_receive_insurance_contract_certification_rel rel on rel.insurance_contract_certification_id = icc.id
--             WHERE rel.insurance_claim_receive_id = icr.id and icc.type = 'vcx'
--             ORDER BY icc.id
--             LIMIT 1
--         ) AS first_certificate ON true
        LEFT JOIN res_province province ON province.id = icr.province_id
        LEFT JOIN res_district district ON district.id = icr.district_id
        LEFT JOIN res_ward ward ON ward.id = icr.ward_id
        WHERE 
--         icr.car_at_scene = false and first_certificate.id is not null
        1=1
    """

    params = [time_zone.key]  # Add time_zone as the first parameter

    if search:
        query += """
            AND (
                gd_chi_tiet.name ILIKE $2
                OR rc.license_plate ILIKE $2
                OR rcb.name ILIKE $2
                OR gd_chi_tiet.name_driver ILIKE $2
                OR CONCAT_WS(', ', 
                    NULLIF(icr.location_damage, ''),
                    NULLIF(ward.name, ''),
                    NULLIF(district.name, ''),
                    NULLIF(province.name, '')
                ) ILIKE $2
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
        headers: Annotated[CommonHeaders, Header()],
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get detailed information about a specific assessment
    """
    time_zone = headers.time_zone
    logger.info(f"timezoneeeeeeeeee {time_zone.key}")
    query = f"""
            SELECT
                gd_chi_tiet.name AS case_number,
                rc.license_plate AS license_plate,
                rcb.name AS vehicle,
                CONCAT_WS(', ', 
                    NULLIF(icr.location_damage, ''),
                    NULLIF(ward.name, ''),
                    NULLIF(district.name, ''),
                    NULLIF(province.name, '')
                ) AS location,
                rpg.display_name AS assessment_address,
                contact.name AS owner_name,
                icr.phone_contact AS phone_number,
                gd_chi_tiet.state AS status,
                icr.description_damage AS incident_desc,
                icr.sequel_damage AS damage_desc,
                TO_CHAR(icr.date_damage AT TIME ZONE 'UTC' AT TIME ZONE $2, 'DD/MM/YYYY - HH24:MI') AS accident_date,
                TO_CHAR(gd_chi_tiet.date AT TIME ZONE 'UTC' AT TIME ZONE $2, 'DD/MM/YYYY - HH24:MI') AS appraisal_date,
                TO_CHAR((icr.date_damage + INTERVAL '3 hours') AT TIME ZONE 'UTC' AT TIME ZONE $2, 'DD/MM/YYYY - HH24:MI') AS complete_time,
                icr.note AS note
            FROM insurance_claim_appraisal_detail gd_chi_tiet
            LEFT JOIN insurance_claim_receive icr ON icr.id = gd_chi_tiet.insur_claim_id
            LEFT JOIN res_partner_gara rpg ON rpg.id = gd_chi_tiet.gara_partner_id
            LEFT JOIN res_partner contact ON contact.id = icr.person_contact_id
            LEFT JOIN res_car rc ON rc.id = gd_chi_tiet.car_id
            LEFT JOIN res_car_brand rcb ON rcb.id = rc.car_brand_id
--             LEFT JOIN LATERAL (
--                 SELECT * FROM insurance_claim_damage icd 
--                 WHERE icd.insur_claim_id = icr.id
--                 ORDER BY icd.id
--                 LIMIT 1
--             ) AS first_damage ON true
--             LEFT JOIN LATERAL (
--                 SELECT * FROM insurance_contract_certification icc 
--                 LEFT JOIN insurance_claim_receive_insurance_contract_certification_rel rel on rel.insurance_contract_certification_id = icc.id
--                 WHERE rel.insurance_claim_receive_id = icr.id and icc.type = 'vcx'
--                 ORDER BY icc.id
--                 LIMIT 1
--             ) AS first_certificate ON true
            LEFT JOIN res_province province ON province.id = icr.province_id
            LEFT JOIN res_district district ON district.id = icr.district_id
            LEFT JOIN res_ward ward ON ward.id = icr.ward_id
            WHERE gd_chi_tiet.id = $1 
--             and icr.car_at_scene = false 
--             and first_certificate.id is not null
        """

    params = [int(assessment_id), time_zone.key]

    assessment_detail = await PostgresDB.execute_query(query, params)
    if assessment_detail:
        assessment_detail = assessment_detail[0]

        # todo: fix hardcode
        assessment_detail['assessment_progress'] = 100
        assessment_detail['status_color'] = color.get(assessment_detail['status'],
                                                      '#757575')  # Default to gray if status not found
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



@router.post("/{assessment_id}/done")
async def done_assessment(
        assessment_id: int,
        current_user: dict = Depends(get_current_user)
):
    """
    Done assessment
    """


    # Xóa các danh mục ảnh hạng mục giám định
    response = await odoo.call_method_post(
        model='insurance.claim.appraisal.detail',
        record_id=assessment_id,
        method='done_assessment',
        token=settings.ODOO_TOKEN,
        kwargs={}
    )
    if response:
        return {
            "id": int(response.get('repair_plan_id')),
            "status": "Success"
        }
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to done assessment")
    
#Xóa các danh mục ảnh hạng mục giám định
@router.delete("/{claim_attachment_category_id}")
async def delete_claim_attachment_category(
        claim_attachment_category_id: int,
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
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    
