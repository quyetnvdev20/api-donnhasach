from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ....database import get_db
from ....models.insurance_detail import InsuranceDetail
from ....models.image import Image
from ....schemas.insurance_detail import InsuranceDetailUpdate
import uuid
from typing import Dict, Any
from datetime import datetime

router = APIRouter()

@router.patch("/images/{image_id}/insurance-detail", response_model=Dict[str, Any])
def update_insurance_detail(
    image_id: uuid.UUID,
    update_data: InsuranceDetailUpdate,
    db: Session = Depends(get_db)
):
    # Lấy image và insurance detail từ database
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
    
    # Cập nhật các trường được cung cấp
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(insurance_detail, field, value)
    
    try:
        db.commit()
        db.refresh(insurance_detail)
        
        # Convert datetime objects to ISO format for JSON response
        response_data = {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in insurance_detail.__dict__.items()
            if not key.startswith('_')
        }
        
        return {
            "status": "success",
            "message": "Insurance detail updated successfully",
            "data": response_data
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error updating insurance detail: {str(e)}"
        ) 