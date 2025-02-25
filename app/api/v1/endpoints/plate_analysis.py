from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from ....database import get_db
from ....models.image import Image
from ....schemas.plate_analysis import PlateDetailResponse, ImageUploadRequest
from ....services.rabbitmq import publish_event
import uuid
import logging
from datetime import datetime
from app.core.settings import ImageStatus, SessionStatus

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/plate-analysis/{plate_number}", response_model=PlateDetailResponse)
async def get_plate_analysis(
    plate_number: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed analysis information for a specific license plate
    """
    # Count images being analyzed for this plate
    analyzing_count = db.query(Image).filter(
        Image.json_data.contains({"plate_number": plate_number}),
        Image.status == ImageStatus.PROCESSING.value
    ).count()
    
    # Count images that need manual tagging
    manual_tagging_count = db.query(Image).filter(
        Image.json_data.contains({"plate_number": plate_number}),
        Image.status == ImageStatus.FAILED.value
    ).count()
    
    # Get the most recent image for this plate
    latest_image = db.query(Image).filter(
        Image.json_data.contains({"plate_number": plate_number})
    ).order_by(Image.created_at.desc()).first()
    
    if not latest_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis found for plate number {plate_number}"
        )
    
    # Count categories (you can define what constitutes a category in your context)
    # For example, if you have different types of analysis or damage categories
    category_count = 3  # Placeholder - replace with actual logic
    
    return PlateDetailResponse(
        plate_number=plate_number,
        analyzing_count=analyzing_count,
        manual_tagging_count=manual_tagging_count,
        category_count=category_count,
        vehicle_image_url=latest_image.image_url
    )

@router.post("/image-analysis", status_code=status.HTTP_202_ACCEPTED)
async def submit_image_for_analysis(
    request: ImageUploadRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Submit an image URL for analysis
    """
    try:
        # Create a new image record with a random session ID
        session_id = str(uuid.uuid1())
        image_id = str(uuid.uuid4())
        new_image = Image(
            id=image_id,
            session_id=session_id,
            image_url=request.image_url,
            status=ImageStatus.PENDING.value
        )
        db.add(new_image)
        db.commit()
        
        # Publish event for Gemini analysis
        await publish_event("image.uploaded", {
            "image_id": image_id,
            "session_id": session_id,
            "image_url": request.image_url,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "status": "success",
            "message": "Image submitted for analysis",
            "image_id": image_id,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Error submitting image for analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit image for analysis: {str(e)}"
        ) 