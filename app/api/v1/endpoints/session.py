import uuid
from datetime import datetime

import aio_pika
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, String
from sqlalchemy.orm import Session

from app.core.settings import SessionStatus, ImageStatus
from .insurance_detail import connect_to_rabbitmq
from ...deps import get_current_user
from ....database import get_db
from ....models.image import Image
from ....models.session import Session as SessionModel
from ....schemas.session import SessionCreate, SessionResponse, SessionListResponse, SessionClose

router = APIRouter()

@router.post("/sessions", response_model=SessionResponse)
def create_session(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Lấy id_keycloak từ token JWT (field 'sub' là standard cho user id)
    id_keycloak = current_user.get('sub')
    if not id_keycloak:
        raise HTTPException(status_code=400, detail="Invalid token: missing user id")

    session = SessionModel(
        status=SessionStatus.NEW,
        created_by=current_user.get("preferred_username", "unknown"),
        id_keycloak=id_keycloak  # Thêm id_keycloak vào session
    )
    
    try:
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating session: {str(e)}"
        )

@router.put("/sessions/{session_id}/open", response_model=SessionResponse)
def open_session(
    session_id: uuid.UUID,
    session_update: SessionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.NEW:
        raise HTTPException(status_code=400, detail="Session can only be opened from NEW status")
    
    session.status = SessionStatus.OPEN
    session.note = session_update.note
    db.commit()
    db.refresh(session)
    return session

@router.put("/sessions/{session_id}/close", response_model=SessionClose)
async def close_session(
    session_id: uuid.UUID,
    quantity_picture: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.OPEN:
        raise HTTPException(status_code=400, detail="Only OPEN session can be closed")

    image_counts = db.query(Image).filter(Image.session_id == session.id).all()

    if len(image_counts) != quantity_picture:
        raise HTTPException(status_code=422, detail="Number of images does not match the quantity of pictures. Please check again.")

    if session.policy_type == 'group_insured':
        # Publish event
        connection = await connect_to_rabbitmq()
        channel = await connection.channel()
        exchange = await channel.declare_exchange("acg.xm.direct", aio_pika.ExchangeType.DIRECT)

        await exchange.publish(
            aio_pika.Message(
                body=json.dumps({
                    "event_type": "IMAGE_PROCESSED",
                    "session_id": str(session.id),
                    "session_type": 'group_insured',
                }).encode(),
                content_type="application/json"
            ),
            routing_key="image.processed"
        )

        await connection.close()
    
    session.status = SessionStatus.CLOSED
    session.closed_at = datetime.utcnow()
    session.closed_by = current_user.get("preferred_username", "unknown")
    db.commit()
    db.refresh(session)
    return session

@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    skip: int = 0,
    limit: int = 100,
    status: SessionStatus = None,
    name: str = None,
    from_date: datetime = None,
    to_date: datetime = None,
    db: Session = Depends(get_db)
):
    # Base query
    query = db.query(SessionModel)
    
    # Apply filters
    if status:
        query = query.filter(SessionModel.status == status)
    
    if name:
        query = query.filter(
            (SessionModel.id.cast(String).ilike(f"%{name}%")) |
            (SessionModel.note.ilike(f"%{name}%")) |
            (SessionModel.created_by.ilike(f"%{name}%"))
        )
        
    if from_date:
        query = query.filter(SessionModel.created_at >= from_date)
        
    if to_date:
        query = query.filter(SessionModel.created_at <= to_date)

    # Order by
    query = query.order_by(
        # SessionModel.status.asc(),
        SessionModel.created_at.desc()
    )
    
    # Get total count before pagination
    total_count = query.count()
    
    # Apply pagination
    sessions = query.offset(skip).limit(limit).all()

    # Count images by status for each session
    for session in sessions:
        status_counts = {
            ImageStatus.PENDING: 0,
            ImageStatus.PROCESSING: 0,
            ImageStatus.COMPLETED: 0,
            ImageStatus.FAILED: 0,
            ImageStatus.INVALID: 0,
            ImageStatus.DONE: 0
        }

        image_counts = (
            db.query(Image.status, func.count(Image.id))
            .filter(Image.session_id == session.id)
            .group_by(Image.status)
            .all()
        )

        for status, count in image_counts:
            status_counts[status] = count

        session.image_status_counts = status_counts

    # Convert model instances to dict for serialization
    session_list = []
    for session in sessions:
        session_dict = {
            "id": session.id,
            "status": session.status,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "created_by": session.created_by,
            "closed_at": session.closed_at,
            "closed_by": session.closed_by,
            "id_keycloak": session.id_keycloak,
            "note": session.note,
            "image_status_counts": session.image_status_counts
        }
        session_list.append(session_dict)

    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "data": session_list
    }

class Session(BaseModel):
    status: SessionStatus = SessionStatus.NEW