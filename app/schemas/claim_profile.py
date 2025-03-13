from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class AssignAppraisalRequest(BaseModel):
    user_id: int
    branch_id: int


class AssignAppraisalResponse(BaseModel):
    success: bool
    message: str


