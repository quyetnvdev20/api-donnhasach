from sqlalchemy import Column, Integer, String, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy import text

from app.models.base import Base


class RepairItem(Base):
    """
    Model to store repair items with their categories.
    The combination of category_id and repair_item_name must be unique.
    """
    __tablename__ = "repair_items"

    id = Column(Integer, primary_key=True, index=True)
    repair_item_name = Column(String, nullable=False)
    category_name = Column(String, nullable=False)
    category_id = Column(Integer, nullable=False)
    
    # Adding created_at and updated_at columns for record keeping
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'), onupdate=func.now())
    
    # Create a unique constraint on the combination of category_id and repair_item_name
    __table_args__ = (
        UniqueConstraint('category_id', 'repair_item_name', name='uq_category_repair_item'),
    ) 