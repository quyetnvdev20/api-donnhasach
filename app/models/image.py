from sqlalchemy import Column, String, DateTime, Enum, UUID, ForeignKey, func, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from .base import Base
import uuid
from app.core.settings import ImageStatus

class Image(Base):
    __tablename__ = "images"

    id = Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(UUID)  # No longer a foreign key
    image_url = Column(String, nullable=False)
    scan_image_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status = Column(Enum(*[status.value for status in ImageStatus], name="imagestatus"), default=ImageStatus.PENDING.value)
    json_data = Column(JSONB, nullable=True)
    error_message = Column(String, nullable=True)
    is_suspecting_wrongly = Column(Boolean, default=False)
    