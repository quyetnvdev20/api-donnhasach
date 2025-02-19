from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ....database import get_db
from ....models.session import Session as SessionModel
from ....schemas.session import SessionCreate, SessionResponse, SessionUpdate
from ....services.rabbitmq import publish_event
from datetime import datetime
from ...deps import get_current_user
import uuid
from sqlalchemy.sql import func
from app.core.settings import SessionStatus
from pydantic import BaseModel

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

@router.put("/sessions/{session_id}/close", response_model=SessionResponse)
def close_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.OPEN:
        raise HTTPException(status_code=400, detail="Only OPEN session can be closed")
    
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

@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    sessions = db.query(SessionModel).offset(skip).limit(limit).all()
    return sessions

class Session(BaseModel):
    status: SessionStatus = SessionStatus.NEW