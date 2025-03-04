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
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[AssessmentListItem])
async def get_assessment_list(
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get list of assessments that need to be processed
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # Mock data for now - in production this would come from a database
    assessments = [
        {
            "license_plate": "30H92087",
            "vehicle": "Mitsubishi Expander",
            "customer_name": "Lê Văn An",
            "assessment_address": "Số 15 đường Trần Phú Phường Tân Thạch Thành phố Nam Kỳ",
            "current_distance": 2.3,
            "notification_time": "01/03/2025 00:00",
            "urgency_level": True,
            "assessment_progress": 25,
            "note": "Khách hàng đang cần giám định gấp tại Gara Ford Đà Nẵng!"
        },
        {
            "license_plate": "30H93333",
            "vehicle": "Mitsubishi Outlander",
            "customer_name": "Nguyễn Văn Sĩ",
            "assessment_address": "Số 15 đường Tân Phú Phường Trấn Thạch Thành phố Nam Kỳ",
            "current_distance": 3.5,
            "notification_time": "01/03/2025 00:00",
            "urgency_level": False,
            "assessment_progress": 0,
            "note": "Khách hàng đang cần giám định gấp tại Gara Ford Đà Nẵng!"
        }
    ]

    return assessments


@router.get("/{assessment_id}", response_model=AssessmentDetail)
async def get_assessment_detail(
        assessment_id: str,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get detailed information about a specific assessment
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

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
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

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
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

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
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

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
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # In a real implementation, you would save the data to the database
    # For now, we'll just return the input data
    return document_collection


@router.get("/{assessment_id}/accident_notification", response_model=DocumentResponse)
async def get_accident_notification(
        assessment_id: str,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get accident notification information
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # Mock data for now - in production this would come from a database
    accident_notification = {
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

    return accident_notification


@router.put("/{assessment_id}/accident_notification", response_model=DocumentResponse)
async def update_accident_notification(
        assessment_id: str,
        document_upload: DocumentUpload,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Update accident notification information
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


@router.get("/{assessment_id}/assessment_report", response_model=DocumentResponse)
async def get_assessment_report(
        assessment_id: str,
        db: Session = Depends(get_db),
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
