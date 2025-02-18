from sqlalchemy import Column, String, DateTime, UUID, ForeignKey, Numeric, Date
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base
import uuid

class InsuranceDetail(Base):
    __tablename__ = "insurance_details"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_id = Column(UUID(as_uuid=True), ForeignKey("images.id"))
    premium_amount = Column(Numeric(precision=10, scale=2))
    owner_name = Column(String(200))
    address = Column(String)
    phone_number = Column(String(20))
    plate_number = Column(String(20))
    chassis_number = Column(String(50))
    engine_number = Column(String(50))
    vehicle_type = Column(String(100))
    insurance_start_date = Column(Date)
    insurance_end_date = Column(Date)
    policy_issued_datetime = Column(DateTime(timezone=True))
    premium_payment_due_date = Column(Date)
    serial_number = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    image = relationship("Image", back_populates="insurance_detail") 