from pydantic import BaseModel, validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class RepairHistoryRequest(BaseModel):
    amount_total: float
    amount_subtotal: float
    amount_tax_total: float
    repair_date: str
    repair_type: str
    vin: str



class RepairHistoryResponse(BaseModel):
    id: int