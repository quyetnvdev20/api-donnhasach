from sqlalchemy import Column, String, DateTime, UUID, ForeignKey, Enum, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base
import uuid
from app.config import ClaimImageStatus
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from sqlalchemy.ext.mutable import MutableDict, MutableList

class Image(Base):
    __tablename__ = "images"

    analysis_id = Column(String, primary_key=True)
    assessment_id = Column(String)
    image_url = Column(String)
    scan_image_url = Column(String) 
    status = Column(Enum(ClaimImageStatus), default=ClaimImageStatus.PENDING)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    error_message = Column(String)
    json_data = Column(MutableDict.as_mutable(JSON))
    list_json_data = Column(MutableList.as_mutable(ARRAY(JSON)))
    keycloak_user_id = Column(String)

    device_token = Column(String)
    results = Column(String)
