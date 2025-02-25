from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from ....database import get_db
from ...deps import get_current_user
from ....models.image import Image
from ....schemas.image_analysis import ImageAnalysisRequest, ImageAnalysisResponse
from ....services.rabbitmq import publish_event
import uuid
import logging
from datetime import datetime
from app.config import ClaimImageStatus
from app.utils.decorators import handle_step_exception

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/image-analysis", response_model=ImageAnalysisResponse)
@handle_step_exception(db_model=Image, id_attr="id", state_attr="status", error_message_attr="error_message")
async def submit_image_for_analysis(
    request: ImageAnalysisRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Submit an image URL for analysis
    """
    # Check exist sub
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Check exist image_id and session_id
    existing_image = db.query(Image).filter(
        Image.image_id == request.image_id,
        Image.session_id == request.session_id
    ).first()
    if existing_image:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image already exists")
    
    new_image = Image(
        image_id=request.image_id,
        session_id=request.session_id,
        image_url=request.image_url,
        keycloak_user_id=current_user.get("sub"),
        status=ClaimImageStatus.PENDING.value
    )
    db.add(new_image)
    db.commit()
    
    # Publish event for Image Analysis Processing Task
    await publish_event(
        exchange_name="image.analysis.direct",
        event_type="image.analysis.processing",
        payload={
            "image_id": request.image_id,
            "session_id": request.session_id,
            "image_url": request.image_url,
            "keycloak_user_id": current_user.get("sub")
        }
    )
    
    return new_image