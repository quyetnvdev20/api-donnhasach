from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Annotated
from pydantic import BaseModel
from datetime import datetime
from ....database import get_db
from ...deps import get_current_user
from ....schemas.assessment import AssessmentListItem, VehicleDetailAssessment, AssessmentDetail, DocumentCollection, \
    DocumentResponse, DocumentUpload, DocumentType, UpdateAssessmentItemResponse, AssessmentStatus, Location, AssignAppraisalRequest, AssignAppraisalResponse
from ....schemas.common import CommonHeaders
from ....utils.erp_db import PostgresDB
from ....utils.distance_calculator import calculate_distance_from_coords_to_address_with_cache, calculate_distance_haversine, format_distance, \
    calculate_distances_batch_from_coords, geocode_address, calculate_distances_batch_from_coords_v2
import json, random
import httpx
import logging
from app.config import settings, odoo
import asyncio
from .assessment_task_status import get_assessment_detail_status, get_collection_document_status, get_accident_notification_status, get_assessment_report_status, get_remote_inspection, get_user_request_remote_inspection

router = APIRouter()
logger = logging.getLogger(__name__)

color = {
    'wait': '#2196F3',
    'done': '#4CAF50',
    'cancel': '#212121',
}

STATE_COLOR = {
    "wait": ("#2196F3", "Đang xử lý"),
    "done": ("#4CAF50", "Đã xử lý"),
    "cancel": ("#212121", "Đã hủy")
}


async def safe_task(coro, name=None, return_if_error=None, timeout=10):
    try:
        return await asyncio.wait_for(coro, timeout)
    except Exception as e:
        logger.error(f"Task '{name or coro}' failed: {e}")
        return return_if_error


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
        WHERE is_display IS TRUE
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
        status: Optional[str] = None,
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
    # TODO: Remove this after testing Latitude and Longitude Tasco
    latitude = headers.latitude or 21.015853129655014
    longitude = headers.longitude or 105.78303779624088
    logger.info(f"latitude: {latitude}, longitude: {longitude}")
    
    # Kiểm tra xem có tọa độ người dùng không
    has_user_location = latitude is not None and longitude is not None
    
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
            (select rp.street
            from res_partner rp
            where rpg.partner_id = rp.id) AS gara_address,
            rpg.display_name AS assessment_address,
            rpg.id AS garage_id,
            TO_CHAR(icr.date_damage AT TIME ZONE 'UTC' AT TIME ZONE %(time_zone)s, 'DD/MM/YYYY - HH24:MI') AS notification_time,
            TO_CHAR((icr.date_damage + INTERVAL '3 hours') AT TIME ZONE 'UTC' AT TIME ZONE %(time_zone)s, 'DD/MM/YYYY - HH24:MI') AS complete_time,
            icr.note AS note,
			(select sum(1) from insurance_claim_remote_inspection where appraisal_detail_id = gd_chi_tiet.id and status != 'cancel') as remote_inspection
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

    # Use named parameters
    params = {"time_zone": time_zone.key}

    if status:
        query += " AND gd_chi_tiet.state = ANY(%(status)s) "
        params["status"] = [s.strip() for s in status.split(',')]

    if search:
        query += """
            AND (
                gd_chi_tiet.name ILIKE %(search)s
                OR rc.license_plate ILIKE %(search)s
                OR rcb.name ILIKE %(search)s
                OR gd_chi_tiet.name_driver ILIKE %(search)s
                OR CONCAT_WS(', ', 
                    NULLIF(icr.location_damage, ''),
                    NULLIF(ward.name, ''),
                    NULLIF(district.name, ''),
                    NULLIF(province.name, '')
                ) ILIKE %(search)s
            )
        """
        params["search"] = f"%{search}%"

    # Add ordering and pagination
    query += f"""
        ORDER BY gd_chi_tiet.id DESC
        LIMIT {limit} OFFSET {offset}
    """

    results = await PostgresDB.execute_query(query, params)
    
    # Tạo danh sách kết quả
    assessment_list = []
    
    # Nếu có tọa độ người dùng, tính khoảng cách hàng loạt
    distances = {}
    if has_user_location:
        try:
            # Lấy danh sách địa chỉ gara từ kết quả
            gara_addresses = [{'address': result.get('gara_address', ''), 'id': result.get('garage_id', '')} for result in results]
            
            # Tính khoảng cách hàng loạt
            distances = await calculate_distances_batch_from_coords_v2(
                float(latitude), float(longitude), gara_addresses, current_user.odoo_token
            )
        except Exception as e:
            logger.error(f"Lỗi khi tính khoảng cách hàng loạt: {str(e)}")
    
    # Xử lý kết quả
    for result in results:
        # Lấy địa chỉ gara
        gara_address = result.get('gara_address', '')
        
        # Lấy khoảng cách và thời gian di chuyển từ kết quả tính hàng loạt
        distance_info = distances.get(gara_address, {"distance": 0.0, "travel_time_minutes": 0})
        distance = distance_info["distance"]
        travel_time_minutes = distance_info["travel_time_minutes"]
        
        # Tạo đối tượng AssessmentListItem
        assessment_item = {
            "id": result["id"],
            "name": result["name"],
            "license_plate": result["license_plate"] or "",
            "vehicle": result["vehicle"] or "",
            "gara_address": result["gara_address"] or "",
            "customer_name": result["customer_name"] or "",
            "assessment_address": result["assessment_address"] or "",
            "location": result.get('location', ''),
            "current_distance": distance,  # Khoảng cách từ vị trí người dùng đến gara
            # "travel_time_minutes": travel_time_minutes,  # Thời gian di chuyển bằng xe máy (phút)
            "notification_time": result["notification_time"] or "",
            "complete_time": result["complete_time"] or "",
            "urgency_level": False,
            "assessment_progress": 0,
            "note": result["note"] or "",
            "status": result["status"] or "",
            "status_color": "#212121"
        }

        status = result['status']

        if headers.invitationCode:
            state_name = 'Giám định từ xa'
            color_code = '2196F3'
        elif result.get('remote_inspection') and status == 'wait':
            state_name = 'Chờ giám định từ xa'
            color_code = '#faad14'
        else:
            state_name = STATE_COLOR.get(status, '#757575')[1] if STATE_COLOR.get(status) else "Đang xử lý"
            color_code = STATE_COLOR.get(status, '#757575')[0] if STATE_COLOR.get(status) else "#2196F3"

        assessment_item['new_status'] = {
            "name": state_name,
            "code": status,
            "color_code": color_code
        }
        
        assessment_list.append(assessment_item)
    
    return assessment_list


@router.get("/{assessment_id}", response_model=AssessmentDetail)
async def get_assessment_detail(
        assessment_id: int,
        headers: Annotated[CommonHeaders, Header()],
        current_user: dict = Depends(get_current_user)
):
    """
    Get detailed information about a specific assessment
    """
    time_zone = headers.time_zone
    latitude, longitude = headers.latitude, headers.longitude
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
                rpg_partner.street AS gara_address,
                contact.name AS owner_name,
                icr.phone_contact AS phone_number,
                gd_chi_tiet.state AS status,
                icr.description_damage AS incident_desc,
                icr.sequel_damage AS damage_desc,
                TO_CHAR(icr.date_damage AT TIME ZONE 'UTC' AT TIME ZONE $2, 'DD/MM/YYYY - HH24:MI') AS accident_date,
                TO_CHAR(gd_chi_tiet.date AT TIME ZONE 'UTC' AT TIME ZONE $2, 'DD/MM/YYYY - HH24:MI') AS appraisal_date,
                TO_CHAR((icr.date_damage + INTERVAL '3 hours') AT TIME ZONE 'UTC' AT TIME ZONE $2, 'DD/MM/YYYY - HH24:MI') AS complete_time,
                icr.note AS note,
                gd_chi_tiet.new_claim_profile_id AS claim_profile_id,
                gd_chi_tiet.insur_claim_id as insur_claim_id,
                crp.name AS assigned_to
            FROM insurance_claim_appraisal_detail gd_chi_tiet
            LEFT JOIN insurance_claim_receive icr ON icr.id = gd_chi_tiet.insur_claim_id
            LEFT JOIN res_partner_gara rpg ON rpg.id = gd_chi_tiet.gara_partner_id
            LEFT JOIN res_partner rpg_partner ON rpg.partner_id = rpg_partner.id
            LEFT JOIN res_partner contact ON contact.id = icr.person_contact_id
            LEFT JOIN res_car rc ON rc.id = gd_chi_tiet.car_id
            LEFT JOIN res_car_brand rcb ON rcb.id = rc.car_brand_id
            LEFT JOIN res_users cru on cru.id = gd_chi_tiet.user_id
            LEFT JOIN res_partner crp on crp.id = cru.partner_id
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

    params = [assessment_id, time_zone.key]

    results = await asyncio.gather(
        safe_task(PostgresDB.execute_query(query, params), name="DB query", return_if_error=[]),
        safe_task(get_assessment_detail_status(assessment_id), name="detail_status", return_if_error={}),
        safe_task(get_collection_document_status(assessment_id), name="collection_status", return_if_error={}),
        safe_task(get_accident_notification_status(assessment_id), name="accident_notification_status", return_if_error={}),
        safe_task(get_assessment_report_status(assessment_id), name="assessment_report_status", return_if_error={}),
        safe_task(get_remote_inspection(assessment_id, headers.invitationCode), name="remote_inspection", return_if_error=[]),
        safe_task(get_user_request_remote_inspection(assessment_id, headers.invitationCode), name="get_user_request_remote_inspection", return_if_error={})
    )

    (
        assessment_detail,
        detail_status,
        collection_status,
        accident_notification_status,
        assessment_report_status,
        remote_inspection_detail,
        user_request
    ) = results

    if assessment_detail:
        assessment_detail = assessment_detail[0]

        if assessment_detail.get('gara_address'):
            try:
                location = await geocode_address(assessment_detail['gara_address'])
                # Only add gara_address as Location if geocoding was successful
                if location and len(location) >= 2:
                    assessment_detail['gara_address'] = Location(lat=location[0], lon=location[1])
                    assessment_detail['gara_distance'] = calculate_distance_haversine(
                        float(latitude), 
                        float(longitude), 
                        location[0], 
                        location[1]
                    )
                else:
                    # Remove gara_address key if geocoding failed
                    assessment_detail.pop('gara_address', None)
                    logger.warning(f"Geocoding failed for address: {assessment_detail.get('gara_address')}")
            except Exception as e:
                # Remove gara_address key if an error occurred during geocoding
                assessment_detail.pop('gara_address', None)
                logger.error(f"Error geocoding address: {str(e)}")
        else:
            # Remove gara_address key if it's null or empty
            assessment_detail.pop('gara_address', None)
            
        assessment_progress = 0
        if detail_status.get("name") == "completed":
            assessment_progress += 25
        if collection_status.get("name") == "completed":
            assessment_progress += 25
        if accident_notification_status.get("name") == "completed":
            assessment_progress += 25
        if assessment_report_status.get("name") == "completed":
            assessment_progress += 25

        assessment_detail['assessment_progress'] = assessment_progress
        assessment_detail['status_color'] = color.get(assessment_detail['status'],
                                                      '#757575')  # Default to gray if status not found
        status = assessment_detail['status']

        if headers.invitationCode:
            state_name = 'Giám định từ xa'
            color_code = '2196F3'
        elif remote_inspection_detail and status == 'wait':
            state_name = 'Chờ giám định từ xa'
            color_code = '#faad14'
        else:
            state_name = STATE_COLOR.get(status, '#757575')[1] if STATE_COLOR.get(status) else "Đang xử lý"
            color_code = STATE_COLOR.get(status, '#757575')[0] if STATE_COLOR.get(status) else "#2196F3"

        assessment_detail['state'] = {
            "name": state_name,
            "code": status,
            "color_code": color_code
        }
        assessment_detail['list_remote_inspection'] = remote_inspection_detail
        if user_request:
            assessment_detail['user_request'] = user_request

        assessment_detail['tasks'] = [{
            "seq": 1,
            "name": "Giám định chi tiết xe",
            "path": "/detail",
            "desc": "Kiểm tra trực tiếp các hạng mục và mực độ tổn thất",
            "icon": "https://example.com",
            "status": {
                "bg_color": "#00000",
                "name": detail_status.get("name"),
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
                    "name": collection_status.get("name"),
                }
            },
            {
                "seq": 3,
                "name": "Thông báo tai nạn & Yêu cầu BT",
                "path": "/accident_notification",
                "desc": "Chia sẻ, in và upload bản kí tươi",
                "icon": "https://example.com",
                "status": {
                    "bg_color": "#00000",
                    "name": accident_notification_status.get("name"),
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
                    "name": assessment_report_status.get("name"),
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
        token=current_user.odoo_token,
        kwargs={}
    )

    return {
        "id": int(response.get('repair_plan_id')),
        "status": "Success"
    }
    
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
            token=current_user.odoo_token
        )

        if response:
            return {
                "id": claim_attachment_category_id,
                "status": "Success"
            }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
#Cập nhật gara sửa chữa
@router.put("/{assessment_id}/update_garage")
async def update_garage(
        assessment_id: int,
        garage_id: int,
        current_user: dict = Depends(get_current_user)
):
    """
    Cập nhật gara sửa chữa
    """
    try:
        
        # Cập nhật gara sửa chữa
        response = await odoo.call_method_post(
            model='insurance.claim.appraisal.detail',
            record_id=assessment_id,
            method='update_garage',
            token=current_user.odoo_token,
            kwargs={'garage_id': garage_id}
        )
        
        return {
            "id": response,
            "status": "Success"
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
@router.post("/{assessment_id}/assign-appraiser", response_model=AssignAppraisalResponse)
async def assign_appraiser(
    assessment_id: int,
    request: AssignAppraisalRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Điều chuyển giám định viên
    
    Parameters:
    - assessment_id: ID GĐCT
    - request: Thông tin giám định viên được điều chuyển
    
    Returns:
    - Kết quả điều chuyển
    """
    try:
        # Gọi API của Odoo để điều chuyển giám định viên
        response = await odoo.call_method_post(
            record_id=assessment_id,
            model='insurance.claim.appraisal.detail',
            method='assign_appraisal_api',
            token=current_user.odoo_token,
            kwargs={
                'user_id': request.user_id,
                'branch_id': request.branch_id,
            }
        )
        return {
            "success": True,
            "message": "Điều chuyển giám định viên thành công"
        }
    
    except Exception as e:
        logger.error(f"Error assigning appraiser: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Điều chuyển giám định viên thất bại: {str(e)}"
        )

@router.get("/{assessment_id}/check-distance")
async def check_distance(
    assessment_id: int,
    headers: Annotated[CommonHeaders, Header()],
    current_user: dict = Depends(get_current_user)
):
    """
    Check distance between user's current location and a garage address
    
    Parameters:
    - assessment_id: ID GĐCT
    - headers: Common headers including user's location (latitude, longitude)
    
    Returns:
    - Distance information and whether it's within allowed limit
    """
    latitude, longitude = headers.latitude, headers.longitude
    
    # Validate user has location data
    if not latitude or not longitude:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User location (latitude and longitude) is required"
        )
    
    try:
        # Get assessment's garage address
        assessment_detail = await PostgresDB.execute_query(
            """
            SELECT rpg_partner.street AS gara_address
            FROM insurance_claim_appraisal_detail gd_chi_tiet
            LEFT JOIN res_partner_gara rpg ON rpg.id = gd_chi_tiet.gara_partner_id
            LEFT JOIN res_partner rpg_partner ON rpg.partner_id = rpg_partner.id
            WHERE gd_chi_tiet.id = $1
            """,
            [assessment_id]
        )
        # Check if assessment detail is found
        if not assessment_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assessment detail not found"
            )
        
        # Get garage coordinates
        location = await geocode_address(assessment_detail[0]['gara_address'])
        
        # Calculate distance
        distance = calculate_distance_haversine(
            float(latitude), 
            float(longitude), 
            location[0], 
            location[1]
        )
        
        # Check if within distance limit
        is_within_limit = distance <= settings.USER_GARAGE_DISTANCE_LIMIT
        
        return {
            "garage_location": Location(lat=location[0], lon=location[1]),
            "current_distance": distance,
            "distance_limit": settings.USER_GARAGE_DISTANCE_LIMIT,
            "is_within_limit": is_within_limit
        }
    except Exception as e:
        logger.error(f"Error checking distance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking distance: {str(e)}"
        )
