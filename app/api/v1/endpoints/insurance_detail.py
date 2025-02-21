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

@router.post("/images/{image_id}/retry", response_model=ImageResponse)
async def retry_process_image(
        image_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    # Kiểm tra image tồn tại
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    # Kiểm tra image đã được xử lý thành công thì không cần retry
    if image.status == ImageStatus.DONE:
        raise HTTPException(
            status_code=400,
            detail="Image already processed successfully"
        )

    try:
        # Reset trạng thái image và lưu trạng thái lỗi cũ
        old_error = image.error_message
        image.status = ImageStatus.PENDING
        image.error_message = None
        image.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(image)

        # Publish event
        connection = await connect_to_rabbitmq()
        channel = await connection.channel()
        exchange = await channel.declare_exchange("acg.xm.direct", aio_pika.ExchangeType.DIRECT)

        await exchange.publish(
            aio_pika.Message(
                body=json.dumps({
                    "event_type": "IMAGE_PROCESSED",
                    "image_id": str(image.id),
                    "session_id": str(image.session_id),
                    "insurance_details": image.json_data,
                    "session_type": "individual_insured",
                    "timestamp": image.updated_at.isoformat()
                }).encode(),
                content_type="application/json"
            ),
            routing_key="image.processed"
        )

        await connection.close()

        # Refresh image để lấy trạng thái mới nhất
        db.refresh(image)
        return image

    except Exception as e:
        db.rollback()
        image.status = ImageStatus.FAILED
        image.error_message = str(e)
        db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Error retrying image: {str(e)}"
        )
