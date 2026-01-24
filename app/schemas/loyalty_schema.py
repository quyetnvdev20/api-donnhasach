from pydantic import BaseModel, Field
from typing import Optional


class LoyaltyProgramsRequest(BaseModel):
    categ_id: int = Field(..., description="ID danh mục dịch vụ")
    appointment_duration: int = Field(..., description="Thời lượng dịch vụ (giờ)")
    amount_total: Optional[float] = Field(default=0.0, description="Tổng số tiền")
    date: str = Field(..., description="Ngày (format: YYYY-MM-DD)")


class LoyaltyProgramByCardRequest(BaseModel):
    code: str = Field(..., description="Mã phiếu giảm giá")
    categ_id: Optional[int] = Field(default=None, description="ID danh mục dịch vụ")
    appointment_duration: int = Field(..., description="Thời lượng dịch vụ (giờ)")
    amount_total: Optional[float] = Field(default=0.0, description="Tổng số tiền")
    date: str = Field(..., description="Ngày (format: YYYY-MM-DD)")

