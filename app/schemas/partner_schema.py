from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class ContactPartnerRequest(BaseModel):
    state_id: int
    ward_id: int
    phone: str
    street: str
    is_default: bool
    name: str
