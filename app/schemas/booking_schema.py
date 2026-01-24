from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class BookingCalculateRequest(BaseModel):
    start_date: str
    start_hours: int
    appointment_duration: int
    categ_id: int
    contact_id: int
    employee_quantity: int
    program_id: Optional[int] = None
    card_id: Optional[int] = None




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

class BookingCancelRequest(BaseModel):
    booking_id: int