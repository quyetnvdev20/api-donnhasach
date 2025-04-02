from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class AssignAppraisalRequest(BaseModel):
    user_id: int
    branch_id: int


class AssignAppraisalResponse(BaseModel):
    success: bool
    message: str


class ApproveLeaveSceneRequest(BaseModel):
    user_receive_id: Optional[int] = None


class ApproveLeaveSceneResponse(BaseModel):
    success: bool
    message: str


