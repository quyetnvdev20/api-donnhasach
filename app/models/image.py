from sqlalchemy import Column, String, DateTime, UUID, ForeignKey, Enum, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base
import uuid
from sqlalchemy.dialects.postgresql import JSONB
from app.core.settings import ImageStatus
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.mutable import MutableDict

class Image(Base):
    __tablename__ = "images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"))
    image_url = Column(String, nullable=False)
    scan_image_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status = Column(Enum(ImageStatus), default=ImageStatus.PENDING)
    json_data = Column(MutableDict.as_mutable(JSON))
    is_suspecting_wrongly = Column(Boolean, nullable=True, server_default='false')

    session = relationship("Session", back_populates="images")
    insurance_detail = relationship("InsuranceDetail", back_populates="image", uselist=False, cascade="all, delete-orphan")

    error_message = Column(String)