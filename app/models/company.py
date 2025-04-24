from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from .base import Base

class Company(Base):
    __tablename__ = "company"

    id = Column(String, primary_key=True)
    code = Column(String)
    name = Column(String)
    db_host = Column(String)
    db_port = Column(String)
    db_name = Column(String)
    backend_host = Column(String)
    backend_port = Column(String)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())