import json
import uuid
from datetime import datetime

import aio_pika
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.settings import ImageStatus, SessionStatus
from .insurance_detail import connect_to_rabbitmq
from ...deps import get_current_user
from ....config import settings
from ....database import get_db
from ....models.image import Image
from ....models.session import Session as SessionModel
from ....schemas.image import ImageResponse
from ....schemas.session import SessionResponse

router = APIRouter()

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def connect_to_rabbitmq():
    """Kết nối tới RabbitMQ với retry logic"""
    return await aio_pika.connect_robust(settings.RABBITMQ_URL)


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


@router.post("/sessions/{session_id}/create", response_model=SessionResponse)
async def create_process_session(
        session_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    # Kiểm tra session tồn tại
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    # Kiểm tra session nếu chưa đóng thì không cho tạo policy
    if session.status != SessionStatus.CLOSED or session.status != SessionStatus.INVALID:
        raise HTTPException(
            status_code=400,
            detail="Session chưa được đóng."
        )

    try:
        # Chuyển trạng thái session thành Chờ xử lý
        session.status = SessionStatus.PENDING
        session.error_message = None
        db.commit()
        db.refresh(session)

        # Publish event
        connection = await connect_to_rabbitmq()
        channel = await connection.channel()
        exchange = await channel.declare_exchange("acg.xm.direct", aio_pika.ExchangeType.DIRECT)

        await exchange.publish(
            aio_pika.Message(
                body=json.dumps({
                    "event_type": "IMAGE_PROCESSED",
                    "session_id": str(session_id),
                    "session_type": "group_insured",
                    "timestamp": session.updated_at.isoformat()
                }).encode(),
                content_type="application/json"
            ),
            routing_key="image.processed"
        )

        await connection.close()

        # Refresh session để lấy trạng thái mới nhất
        db.refresh(session)
        return session

    except Exception as e:
        db.rollback()
        session.status = SessionStatus.FAILED
        session.error_message = str(e)
        db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Error retrying image: {str(e)}"
        )
