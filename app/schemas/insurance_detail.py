from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InsuranceDetailUpdate(BaseModel):
    owner_name: Optional[str] = None
    number_seats: Optional[int] = None
    liability_amount: Optional[float] = None
    accident_premium: Optional[float] = None
    address: Optional[str] = None
    plate_number: Optional[str] = None
    phone_number: Optional[str] = None
    chassis_number: Optional[str] = None
    engine_number: Optional[str] = None
    vehicle_type: Optional[str] = None
    insurance_start_date: Optional[datetime] = None
    insurance_end_date: Optional[datetime] = None
    premium_amount: Optional[float] = None
    policy_issued_datetime: Optional[datetime] = None 
    premium_payment_due_date: Optional[datetime] = None
    serial_number: Optional[str] = None
    note: Optional[str] = None