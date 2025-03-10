from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class Label(BaseModel):
    name: str
    code: str
    color_code: str


class Status(BaseModel):
    name: str
    code: str
    color_code: str


class Part(BaseModel):
    name: str
    quantity: int
    unit_price: float
    total_price: float


class RepairPlanDetail(BaseModel):
    name: str
    parts: List[Part]
    description: str
    garage_price: float
    suggested_price: float
    discount_percentage: float


class RepairItem(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    id: Optional[int] = None


class RepairType(BaseModel):
    name: str
    code: str
    color_code: str


class RepairGarageLocation(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None


class RepairPlanDetailItem(BaseModel):
    name: str
    item: RepairItem = None
    type: RepairType = None
    garage_price: float = None
    suggested_price: float = None
    discount_percentage: float = None


class RepairPlanApprovalRequest(BaseModel):
    quote_photo_url: Optional[str] = None
    vehicle_name: str = None
    repair_garage_location: RepairGarageLocation = None
    inspection_date: Optional[str] = None
    approval_deadline: Optional[str] = None
    status: Status = None
    label: Label = None
    repair_plan_details: List[RepairPlanDetailItem]


class RepairPlanApprovalResponse(BaseModel):
    id: int


class RepairPlanListItem(BaseModel):
    file_name: Optional[str] = None
    id: int
    vehicle_info: str
    owner_name: Optional[str] = None
    repair_garage_location: RepairGarageLocation
    inspection_date: Optional[str] = None
    location_damage: Optional[str] = None
    submitter: Optional[str] = None
    status: Status
    label: Label
    total_cost: Optional[dict] = None


class RepairPlanListResponse(BaseModel):
    data: List[RepairPlanListItem]


class ApprovalHistory(BaseModel):
    reason: str
    approval_time: str


class RepairPlanAwaitingDetail(BaseModel):
    file_name: Optional[str] = None
    contract_number: Optional[str] = None
    vehicle_info: Optional[str] = None
    repair_garage_location: RepairGarageLocation
    inspection_date: Optional[str] = None
    approval_deadline: Optional[str] = None
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    status: Status
    approval_history: List[ApprovalHistory] = None
    repair_plan_details: List[RepairPlanDetailItem]
    amount_subtotal: float
    amount_discount: float
    amount_untaxed_total: float


class RepairPlanDetailResponse(BaseModel):
    data: RepairPlanAwaitingDetail


class RepairPlanApproveRequest(BaseModel):
    repair_id: int
    approve_reason: str


class RepairPlanApproveResponse(BaseModel):
    id: int


class RepairPlanRejectRequest(BaseModel):
    repair_id: int
    reject_reason: str


class RepairPlanRejectResponse(BaseModel):
    id: int


class RepairCategory(BaseModel):
    code: str
    name: str
    color_code: str


class RepairCategoryAppraisal(BaseModel):
    id: Optional[int]
    name: str = None
    code: str = None

class RepairCategoryResponse(BaseModel):
    data: List[RepairCategoryAppraisal] = []
