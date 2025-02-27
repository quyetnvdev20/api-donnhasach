from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from ....database import get_db
from ...deps import get_current_user
from ....models.image import Image
from ....schemas.image_analysis import ImageAnalysisRequest, ImageAnalysisResponse
from ....services.rabbitmq import publish_event
from ....services.firebase import FirebaseNotificationService
from ....utils.erp_db import PostgresDB
import httpx
import json
import uuid
import logging
from datetime import datetime
from app.config import ClaimImageStatus, settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/assessment/{assessment_id}/analysis/rmqasync",
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
        auto_analysis=request.auto_analysis,
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
    images = db.query(Image).filter(Image.analysis_id == "17406439285770").all()
    for image in images:
        
        await publish_event(
        exchange_name="image.analysis.direct",
        routing_key="image.uploaded",
        payload={
            "analysis_id": image.analysis_id,
            "assessment_id": image.assessment_id,
            "image_url": image.image_url,
            "keycloak_user_id": image.keycloak_user_id,
            "auto_analysis": image.auto_analysis
        }
    )
    return {"message": "success"}

@router.post("/assessment/{assessment_id}/analysis/upload",
             response_model=ImageAnalysisResponse)
async def process_image_analysis(
    assessment_id: str,
    request: ImageAnalysisRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Process image analysis directly without using RabbitMQ
    """
    # Check authorization
    if not current_user.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )
    
    # Check for existing image
    existing_image = db.query(Image).filter(
        Image.analysis_id == str(request.analysis_id or request.image_id),
        Image.id == str(request.image_id),
        Image.assessment_id == str(assessment_id),
    ).first()
    
    if existing_image:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image already exists"
        )
    
    # Create new image record
    new_image = Image(
        analysis_id=str(request.analysis_id or request.image_id),
        assessment_id=str(assessment_id),
        image_url=request.image_url,
        id=str(request.image_id),
        device_token=request.device_token,
        keycloak_user_id=current_user.get("sub"),
        auto_analysis=request.auto_analysis,
        status=ClaimImageStatus.PROCESSING.value
    )
    db.add(new_image)
    db.commit()
    db.refresh(new_image)

    try:
        # Process image using httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.INSURANCE_PROCESSING_API_URL}/claim-image/claim-image-process",
                json={"image_url": new_image.image_url},
                headers={
                    "x-api-key": settings.CLAIM_IMAGE_PROCESS_API_KEY,
                    "Content-Type": "application/json",
                },
                timeout=settings.CLAIM_IMAGE_PROCESS_TIMEOUT
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to process image analysis: {response.text}"
                )

            # Update image with results
            new_image.status = ClaimImageStatus.SUCCESS.value
            new_image.list_json_data = response.json().get("data", [])
            db.commit()
            db.refresh(new_image)

            # Map assessment items
            mapped_results = []
            if new_image.list_json_data:
                # Transform and map the data
                transformed_items = []
                for data_dict in new_image.list_json_data:
                    for category, state in data_dict.items():
                        transformed_items.append({
                            "damage_name": state,
                            "item_name": category
                        })

                if transformed_items:
                    # Build query
                    placeholders = []
                    values = []
                    for i, item in enumerate(transformed_items):
                        placeholders.append(f"(iclc.name = ${2*i + 1} AND isc.name = ${2*i + 2})")
                        values.extend([item["item_name"], item["damage_name"]])

                    query = f"""
                        SELECT 
                            iclc.id AS category_id,
                            isc.id AS state_id,
                            iclc.name AS category_name,
                            isc.name AS state_name
                        FROM insurance_claim_list_category iclc
                        JOIN insurance_state_category isc ON 1=1
                        WHERE {' OR '.join(placeholders)};
                    """

                    results = await PostgresDB.execute_query(query, values)
                    
                    if results:
                        result_map = {
                            (row["category_name"], row["state_name"]): {
                                "damage_id": row["state_id"],
                                "item_id": row["category_id"]
                            } for row in results
                        }

                        for item in transformed_items:
                            key = (item["item_name"], item["damage_name"])
                            if key in result_map:
                                item.update(result_map[key])
                                mapped_results.append(item)

                new_image.results = json.dumps(mapped_results)
                db.commit()

            # Send notification
            notification_data = {
                "analysis_id": new_image.analysis_id,
                "assessment_id": new_image.assessment_id,
                "image_id": str(new_image.id),
                "image_url": str(new_image.image_url),
                "auto_analysis": str(new_image.auto_analysis),
                "results": json.dumps(mapped_results)
            }

            await FirebaseNotificationService.send_notification_to_topic(
                topic=f'tic_claim_{str(new_image.keycloak_user_id)}',
                title="Image Analysis Complete",
                body="Your image has been successfully analyzed.",
                data=notification_data
            )

    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        new_image.status = ClaimImageStatus.FAILED.value
        new_image.error_message = str(e)
        db.commit()

        # Send failure notification
        await FirebaseNotificationService.send_notification_to_topic(
            topic=f'tic_claim_{str(new_image.keycloak_user_id)}',
            title="Image Analysis Failed",
            body="There was an error analyzing your image.",
            data={
                "analysis_id": new_image.analysis_id,
                "assessment_id": new_image.assessment_id,
                "image_id": str(new_image.id),
                "image_url": str(new_image.image_url),
                "auto_analysis": str(new_image.auto_analysis),
                "results": json.dumps([])
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    return new_image