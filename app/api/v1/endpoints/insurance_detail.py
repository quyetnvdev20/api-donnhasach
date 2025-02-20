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
from ....workers.image_processor import process_message

router = APIRouter()

@router.patch("/images/{image_id}/insurance-detail", response_model=Dict[str, Any])
def update_insurance_detail(
    image_id: uuid.UUID,
    update_data: InsuranceDetailUpdate,
    db: Session = Depends(get_db)
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
        # Reset trạng thái image
        image.status = ImageStatus.PENDING
        image.error_message = None
        image.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(image)

        # Tạo message để xử lý
        message = aio_pika.Message(
            body=json.dumps({
                "event_type": "IMAGE_RETRY",
                "image_id": str(image.id),
                "session_id": str(image.session_id),
                "image_url": str(image.image_url),
                "retry_by": current_user.get("preferred_username", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }).encode(),
            content_type="application/json"
        )

        # Gọi process_message để xử lý
        await process_message(message)

        # Refresh image để lấy trạng thái mới nhất
        db.refresh(image)

        return image

    except Exception as e:
        db.rollback()
        # Cập nhật trạng thái lỗi
        image.status = ImageStatus.FAILED
        image.error_message = str(e)
        db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Error retrying image: {str(e)}"
        )
