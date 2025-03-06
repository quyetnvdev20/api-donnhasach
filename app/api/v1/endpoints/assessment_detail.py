from fastapi import APIRouter, Depends, HTTPException, status
from ...deps import get_current_user
from ....schemas.assessment import VehicleDetailAssessment, UpdateAssessmentItemResponse
from ....utils.erp_db import PostgresDB
import json
import logging
from app.config import settings, odoo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{assessment_id}/detail", response_model=VehicleDetailAssessment)
async def get_vehicle_detail_assessment(
        assessment_id: int,
        current_user: dict = Depends(get_current_user)
):
    """
    Get detailed vehicle assessment information
    """
    # Thực hiện một truy vấn duy nhất để lấy cả danh mục và hình ảnh
    query = f"""
    WITH category_data AS (
        SELECT 
            ica.id,
            ica.category_id, 
            iclc.name as category_name,
            ica.status,
            isc.name as status_name,
            ica.solution as solution_code,
            to_char(ica.date, 'dd/mm/YYYY') as date           
        FROM insurance_claim_attachment_category ica
        LEFT JOIN insurance_type_document itd ON ica.type_document_id = itd.id
        LEFT JOIN insurance_state_category isc ON ica.status = isc.id
        LEFT JOIN insurance_claim_list_category iclc ON ica.category_id = iclc.id
        WHERE detail_category_id = $1
    ),
    image_data AS (
        SELECT 
            ica.category_id,
            ica.id,
            ica.link_preview as link,
            ica.location,
            ica.lat,
            ica.long,
            to_char(ica.date_upload, 'dd/mm/YYYY hh:mm:ss') as date_upload
        FROM insurance_claim_attachment ica
        WHERE ica.category_id IN (SELECT id FROM category_data)
    )
    SELECT 
        cd.id,
        cd.category_id,
        cd.category_name,
        cd.status,
        cd.status_name,
        cd.solution_code,
        cd.date,
        json_agg(
            json_build_object(
                'id', id.id,
                'link', id.link,
                'location', id.location,
                'lat', id.lat,
                'long', id.long,
                'date', id.date_upload
            )
        ) FILTER (WHERE id.id IS NOT NULL) as images
    FROM category_data cd
    LEFT JOIN image_data id ON cd.id = id.category_id
    GROUP BY cd.id, cd.category_id, cd.category_name, cd.status, cd.status_name, cd.solution_code, cd.date
    """

    # Thực thi truy vấn
    results = await PostgresDB.execute_query(query, [assessment_id])
    assessment_detail = []

    if results:
        # Xử lý kết quả
        for item in results:
            item_id = item.get('id')
            
            # Lấy danh sách hình ảnh từ kết quả JSON và chuyển đổi thành list các dict
            images_json = item.get('images')
            list_image = []
            
            # Kiểm tra nếu images_json không phải None và không phải list rỗng
            if images_json and images_json != '[null]':
                # Nếu images_json đã là list, sử dụng trực tiếp
                if isinstance(images_json, list):
                    list_image = images_json
                # Nếu images_json là string JSON, parse nó
                elif isinstance(images_json, str):
                    try:
                        list_image = json.loads(images_json)
                        # Loại bỏ các giá trị null nếu có
                        list_image = [img for img in list_image if img is not None]
                    except json.JSONDecodeError:
                        logger.error(f"Error parsing JSON: {images_json}")
                        list_image = []
            
            # Xây dựng đối tượng chi tiết đánh giá
            assessment_detail.append({
                'id': item_id,
                'category_id': {
                    'id': item.get('category_id'),
                    'name': item.get('category_name'),
                },
                'state': {
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
            'status': item.state.id,
            # TODO: hardcode solution code
            'solution': 'repair',
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update assessment detail")
