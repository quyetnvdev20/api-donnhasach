from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime


class ExtraProductItem(BaseModel):
    product_id: int
    quantity: int


class BookingCalculateRequest(BaseModel):
    start_date: str
    start_hours: int
    appointment_duration: int
    categ_id: int
    contact_id: int
    employee_quantity: int
    program_id: Optional[int] = None
    card_id: Optional[int] = None
    extra_data: Optional[List[ExtraProductItem]] = None




class BookingCreateRequest(BaseModel):
    start: str
    start_hours: int
    required_staff_qty: int
    appointment_duration: int
    categ_id: Optional[int] = None
    partner_id: Optional[int] = None
    contact_id: int
    is_recurring_service: bool = False
    recurring_interval: Optional[int] = None
    recurring_unit: Optional[str] = None
    assigned_staff_ids: Optional[List[int]] = None
    program_id: Optional[int] = None
    card_id: Optional[int] = None
    description: Optional[str] = None
    extra_data: Optional[List[ExtraProductItem]] = None

class BookingCancelRequest(BaseModel):
    booking_id: int


class CalculateCleaningDatesRequest(BaseModel):
    weekday: int = Field(..., description="Thứ trong tuần (0=Thứ 2, 1=Thứ 3, ..., 5=Thứ 7, 6=CN)")
    package_id: int = Field(..., description="ID của gói định kỳ")
    start_date: Optional[str] = Field(None, description="Ngày bắt đầu (YYYY-MM-DD), mặc định là hôm nay")


class PeriodicPricingRequest(BaseModel):
    dates: List[str] = Field(..., description="Danh sách ngày dọn dẹp (YYYY-MM-DD)")
    start_hours: int = Field(..., description="Giờ bắt đầu")
    appointment_duration: int = Field(..., description="Thời gian dịch vụ (giờ)")
    categ_id: int = Field(..., description="ID danh mục dịch vụ")
    contact_id: int = Field(..., description="ID địa chỉ liên hệ")
    employee_quantity: int = Field(..., description="Số lượng nhân viên")
    program_id: Optional[int] = None
    card_id: Optional[int] = None
    extra_data: Optional[List[ExtraProductItem]] = None