from sqlalchemy import Column, String, DateTime, UUID, Text, Enum, Integer
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base
import uuid
from sqlalchemy.dialects.postgresql import JSONB
from app.core.settings import SessionStatus

class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_keycloak = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status = Column(Enum(SessionStatus), default=SessionStatus.NEW)
    note = Column(Text)
    policy_type = Column(String(100))
    created_by = Column(String(100), nullable=False)
    closed_at = Column(DateTime(timezone=True))
    closed_by = Column(String(100))
    responsible_id = Column(Integer())
    responsible_name = Column(Text)
    partner_channel_id = Column(Integer())
    partner_channel_name = Column(Text)

    images = relationship("Image", back_populates="session", cascade="all, delete-orphan")
    error_message = Column(String)