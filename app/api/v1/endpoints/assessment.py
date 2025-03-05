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

    # Mock data for now - in production this would come from a database
    vehicle_detail = {
        "assessment_id": int(assessment_id),
        "items": [
            {
                "id": 6425,
                "name": "Cửa trước trái",
                "damage": {
                    "id": 55,
                    "name": "Móp méo, cong vênh"
                },
                "images": [
                    {
                        "date": "28/02/2025 02:02:18",
                        "id": 117352,
                        "lat": None,
                        "link": "https://dev-storage.baohiemtasco.vn/forum.carpla.online/tic-store/1740623866712237_32_1740623866651245_compressed_image_CAP_F8F24AA2-C9B6-4791-BE6E-3CFB93841BD5.png",
                        "location": None,
                        "long": None
                    },
                    {
                        "date": "28/02/2025 02:02:18",
                        "id": 117353,
                        "lat": None,
                        "link": "https://dev-storage.baohiemtasco.vn/forum.carpla.online/tic-store/1740623915572745_69_1740623915511677_compressed_image_CAP_9C189B67-549F-4D4D-8184-A9C096AF3309.png",
                        "location": None,
                        "long": None
                    }
                ]
            }
        ]
    }

    return vehicle_detail


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
