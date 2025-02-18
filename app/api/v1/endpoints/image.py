from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ....database import get_db
from ....models.image import Image
from ....models.session import Session as SessionModel
from ....schemas.image import ImageCreate, ImageResponse, SessionImagesResponse, ImageUrlRequest
from ....services.rabbitmq import publish_event
from ...deps import get_current_user
import uuid
from pydantic import BaseModel
from ....workers.image_processor import process_image

router = APIRouter()

@router.post("/sessions/{session_id}/images", response_model=ImageResponse)
async def upload_image(
    session_id: uuid.UUID,
    image: ImageCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Kiểm tra session tồn tại và đang ở trạng thái OPEN
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "OPEN":
        raise HTTPException(status_code=400, detail="Session is not open")

    # Tạo record image mới
    db_image = Image(
        session_id=session_id,
        image_url=str(image.image_url),
        status="NEW"
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    # Bắn event để xử lý ảnh
    await publish_event(
        "image.uploaded",
        {
            "event_type": "IMAGE_UPLOADED",
            "image_id": str(db_image.id),
            "session_id": str(session_id),
            "image_url": str(image.image_url),
            "timestamp": db_image.created_at.isoformat()
        }
    )

    return db_image

@router.get("/sessions/{session_id}/images", response_model=List[ImageResponse])
def list_session_images(
    session_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return db.query(Image).filter(Image.session_id == session_id).all()

@router.get("/images/{image_id}", response_model=ImageResponse)
def get_image(
    image_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return image

@router.get("/sessions/{session_id}/urls", response_model=SessionImagesResponse)
def get_session_image_urls(
    session_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    images = db.query(Image).filter(Image.session_id == session_id).all()
    
    return SessionImagesResponse(
        session_id=session_id,
        status=session.status,
        image_urls=[image.image_url for image in images],
        total_images=len(images)
    )


# Add new endpoint
@router.post("/images/chat_gpt")
async def process_image_with_chatgpt(
    request: ImageUrlRequest
):
    try:
        # Call process_image function from image_processor
        result = await process_image(request.image_url)
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing image: {str(e)}"
        )
