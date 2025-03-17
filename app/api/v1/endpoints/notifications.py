from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from ....database import get_db
from ...deps import get_current_user
from ....models.image import Image
from ....services.firebase import FirebaseNotificationService
from pydantic import BaseModel

router = APIRouter()

class NotificationRequest(BaseModel):
    device_token: Optional[str] = None
    topic: Optional[str] = None
    title: str
    body: str
    data: Optional[Dict[str, str]] = None

class NotificationResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict] = None

@router.post("/send-notification", response_model=NotificationResponse)
async def send_notification(
    request: NotificationRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Send a notification to a device or topic
    """
    # Check if user is authenticated
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Validate request - must have either device_token or topic
    if not request.device_token and not request.topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Either device_token or topic must be provided"
        )
    
    try:
        # Send notification based on whether device_token or topic is provided
        result = await FirebaseNotificationService.send_notification_to_topic(
            topic=request.topic,
            title=request.title,
            body=request.body,
            data=request.data
        )

        if result["success"]:
            return {
                "success": True,
                "message": "Notification sent successfully",
                "details": result.get("response")
            }
        else:
            return {
                "success": False,
                "message": "Failed to send notification",
                "details": result.get("error")
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending notification: {str(e)}"
        )

@router.post("/notify-by-image-id/{image_id}", response_model=NotificationResponse)
async def notify_by_image_id(
    image_id: str,
    notification: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Send a notification to the device associated with a specific image
    """
    # Check if user is authenticated
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Get the image from database
    image = db.query(Image).filter(Image.image_id == image_id).first()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with ID {image_id} not found"
        )
    
    # Check if device token is available
    if not image.device_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No device token associated with image ID {image_id}"
        )
    
    try:
        # Send notification to the device
        result = await FirebaseNotificationService.send_notification_to_device(
            device_token=image.device_token,
            title=notification.get("title", "Notification"),
            body=notification.get("body", ""),
            data=notification.get("data")
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Notification sent successfully to device for image {image_id}",
                "details": result.get("response")
            }
        else:
            return {
                "success": False,
                "message": "Failed to send notification",
                "details": result.get("error")
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending notification: {str(e)}"
        ) 