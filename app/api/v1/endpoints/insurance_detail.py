from app.api.deps import get_current_user
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ....database import get_db
from ....models.insurance_detail import InsuranceDetail
from ....models.image import Image
from ....schemas.insurance_detail import InsuranceDetailUpdate
from ....schemas.image import ImageResponse
from app.core.settings import ImageStatus
import uuid
from typing import Dict, Any
from datetime import datetime
import aio_pika
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from ....config import settings
from ....models.session import Session as SessionModel

router = APIRouter()

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def connect_to_rabbitmq():
    """Kết nối tới RabbitMQ với retry logic"""
    return await aio_pika.connect_robust(settings.RABBITMQ_URL)

@router.patch("/images/{image_id}/insurance-detail", response_model=Dict[str, Any])
def update_insurance_detail(
        image_id: uuid.UUID,
        update_data: InsuranceDetailUpdate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    # Lấy image từ database
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    session = db.query(SessionModel).filter(SessionModel.id == str(image.session_id)).first()

    insurance_detail = db.query(InsuranceDetail).filter(
        InsuranceDetail.image_id == image_id
    ).first()

    if not insurance_detail:
        raise HTTPException(
            status_code=404,
            detail="Insurance detail not found for this image"
        )

    try:
        # Cập nhật insurance_detail
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(insurance_detail, field, value)

        # Cập nhật json_data của image
        current_json_data = image.json_data or {}
        # Chuyển đổi datetime objects thành ISO format để có thể serialize
        update_json = {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in update_dict.items()
        }
        current_json_data.update(update_json)
        image.json_data = current_json_data

        # Lưu các thay đổi vào database
        db.commit()
        db.refresh(insurance_detail)
        db.refresh(image)

        # Chuẩn bị response
        response_data = {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in insurance_detail.__dict__.items()
            if not key.startswith('_')
        }

        return {
            "status": "success",
            "message": "Insurance detail updated successfully",
            "data": response_data,
            "json_data": image.json_data  # Thêm json_data vào response
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error updating insurance detail: {str(e)}"
        )
