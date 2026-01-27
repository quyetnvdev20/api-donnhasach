from pydantic import BaseModel, Field
from typing import Optional, List


class ExtraProductItem(BaseModel):
    product_id: int
    quantity: int


class BookingContractCreateRequest(BaseModel):
    dates: List[str] = Field(..., description="Danh sách ngày dọn dẹp (YYYY-MM-DD)")
    start_hours: int = Field(..., description="Giờ bắt đầu")
    required_staff_qty: int = Field(..., description="Số lượng nhân viên")
    appointment_duration: int = Field(..., description="Thời gian dịch vụ (giờ)")
    categ_id: int = Field(..., description="ID danh mục dịch vụ")
    contact_id: int = Field(..., description="ID địa chỉ liên hệ")
    package_id: int = Field(..., description="ID của gói định kỳ")
    base_amount: float = Field(..., description="Tổng tiền cơ bản của gói")
    extra_amount: float = Field(..., description="Tổng tiền dịch vụ thêm của gói")
    program_id: Optional[int] = None
    card_id: Optional[int] = None
    description: Optional[str] = None
    extra_data: Optional[List[ExtraProductItem]] = None

