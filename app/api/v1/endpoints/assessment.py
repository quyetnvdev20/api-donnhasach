from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from ....database import get_db
from ...deps import get_current_user
from ....schemas.assessment import AssessmentListItem, VehicleDetailAssessment, AssessmentDetail, DocumentCollection, \
    DocumentResponse, DocumentUpload
from ....utils.erp_db import PostgresDB
import json
import httpx
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

color = {
    'wait': '#2196F3',
    'done': '#4CAF50',
    'cancel': '#212121',
}

# Khởi tạo đối tượng Odoo với config
config = {
    'ODOO_URL': os.getenv('ODOO_URL', settings.ODOO_URL),
    'ODOO_TOKEN': os.getenv('ODOO_TOKEN', settings.ODOO_TOKEN)
}
odoo = Odoo(config=config)


@router.get("", response_model=List[AssessmentListItem])
async def get_assessment_list(
        search: Optional[str] = None,
        page: int = 1,
        size: int = 10,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get list of assessments that need to be processed
    """
    query = f"""
        SELECT
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
    LIMIT {size} OFFSET {(page - 1) * size}
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

    # Mock data for now - in production this would come from a database
    assessment_detail = {
        "case_number": "BH-203421",
        "vehicle": "Mitsubishi Expander - 30H92312",
        "location": "Mitsubishi Quảng Nam",
        "owner_name": "Trần Đức Hạnh",
        "phone_number": "0942216765",
        "accident_date": "01/01/2025 00:00",
        "incident_desc": "Va quẹt với cây",
        "damage_desc": "Nắp ca pô bị trầy",
        "assessment_progress": 0,
        "note": "",
        "tasks": [
            {
                "seq": 1,
                "id": 1,
                "name": "Giám định chi tiết xe",
                "path": "/detail",
                "desc": "Kiểm tra trực tiếp các hạng mục và mực độ tổn thất",
                "icon": "https://example.com",
                "status": {
                    "bg_color": "#00000",
                    "name": "not_start",
                }
            },
            {
                "seq": 2,
                "id": None,
                "name": "Thu thập hồ sơ",
                "path": "/collect_document",
                "desc": "Chụp và trích xuất thông tin từ giấy tờ cần thiết",
                "icon": "https://example.com",
                "status": {
                    "bg_color": "#00000",
                    "name": "not_start",
                }
            },
            {
                "seq": 3,
                "id": None,
                "name": "Upload Thông tin tai nạn & Yêu cầu BT",
                "path": "/accident_notification",
                "desc": "Chia sẻ, in và upload bản kí tươi",
                "icon": "https://example.com",
                "status": {
                    "bg_color": "#00000",
                    "name": "not_start",
                }
            },
            {
                "seq": 4,
                "id": None,
                "name": "Upload Biên bản giám định & Xác định thiệt hại",
                "path": "/assessment_report",
                "desc": "Chia sẻ, in và upload bản kí tươi",
                "icon": "https://example.com",
                "status": {
                    "bg_color": "#00000",
                    "name": "not_start",
                }
            }
        ]
    }

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
            ica.type, 
            ica.type_document_id, 
            itd.name as type_document_name,
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


@router.put("/{assessment_id}/detail", response_model=VehicleDetailAssessment)
async def update_vehicle_detail_assessment(
        assessment_id: str,
        vehicle_detail: VehicleDetailAssessment,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Update vehicle detail assessment information
    """

    # In a real implementation, you would save the data to the database
    # For now, we'll just return the input data
    return vehicle_detail


@router.get("/{assessment_id}/collect_document", response_model=DocumentCollection)
async def get_document_collection(
        assessment_id: str,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get document collection information
    """

    # Mock data for now - in production this would come from a database
    document_collection = {
        "name_driver": "Nguyễn văn An",
        "phone_driver": "0918515121",
        "cccd": None,
        "gender_driver": None,
        "gplx_effect_date": None,
        "gplx_expired_date": None,
        "gplx_level": None,
        "gplx_no": None,
        "registry_date": None,
        "registry_expired_date": None,
        "registry_no": None,
        "documents": [
            {
                "type_document_id": 1,
                "type": "",
                "name": "",
                "desc": "",
                "images": [
                    {
                        "date": "27/02/2025 11:02:09",
                        "description": "Chụp mặt trước & sau, rõ nét, đọc được thông tin",
                        "id": 117348,
                        "lat": "21.004388702201652",
                        "link": "https://dev-storage.baohiemtasco.vn/forum.carpla.online/tic-store/1740672577458314_9_1740672577398258_compressed_image_1740672577263_claim.png",
                        "location": "Q. Thanh Xuân, Thành Phố Hà Nội, Việt Nam",
                        "long": "105.80242028756557",
                        "thumbnail": "https://file-cdn.baohiemtasco.vn/insurance-data/car-video-thumb.jpeg"
                    }
                ]
            },
            {
                "type_document_id": 1,
                "type": "",
                "name": "",
                "desc": "",
                "images": [
                    {
                        "date": "27/02/2025 11:02:09",
                        "description": "Chụp mặt trước & sau, rõ nét, đọc được thông tin",
                        "id": 117348,
                        "lat": "21.004388702201652",
                        "link": "https://dev-storage.baohiemtasco.vn/forum.carpla.online/tic-store/1740672577458314_9_1740672577398258_compressed_image_1740672577263_claim.png",
                        "location": "Q. Thanh Xuân, Thành Phố Hà Nội, Việt Nam",
                        "long": "105.80242028756557",
                        "thumbnail": "https://file-cdn.baohiemtasco.vn/insurance-data/car-video-thumb.jpeg"
                    }
                ]
            }
        ]
    }

    return document_collection


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
