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
from app.workers.image_processor import mapping_assessment_item

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/assessment/{assessment_id}/analysis/upload",
             response_model=ImageAnalysisResponse)
async def submit_image_for_analysis(
    assessment_id: str,
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
        Image.analysis_id == str(request.analysis_id or request.image_id),
        Image.id == str(request.image_id),
        Image.assessment_id == str(assessment_id),
    ).first()
    if existing_image:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Image already exists")
    
    new_image = Image(
        analysis_id=str(request.analysis_id or request.image_id),
        assessment_id=str(assessment_id),
        image_url=request.image_url,
        id=str(request.image_id),
        device_token=request.device_token,
        keycloak_user_id=current_user.get("sub"),
        status=ClaimImageStatus.PENDING.value
    )
    db.add(new_image)
    db.commit()
    
    # Publish event for Image Analysis Processing Task
    await publish_event(
        exchange_name="image.analysis.direct",
        routing_key="image.uploaded",
        payload={
            "analysis_id": str(request.analysis_id or request.image_id),
            "assessment_id": str(assessment_id),
            "image_url": request.image_url,
            "keycloak_user_id": current_user.get("sub")
        }
    )
    
    return new_image

@router.get("/assessment/test")
async def test(
    db: Session = Depends(get_db)
):
    image = db.query(Image).filter(Image.id == "17405629615708").first()
    return await mapping_assessment_item(image.list_json_data)