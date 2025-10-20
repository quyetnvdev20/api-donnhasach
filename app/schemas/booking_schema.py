from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class BookingCalculateRequest(BaseModel):
    start_date: str
    start_hours: int
    appointment_duration: int
    categ_id: int
    contact_id: int