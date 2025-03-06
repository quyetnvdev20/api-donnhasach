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
    name: str
    id: int


class RepairType(BaseModel):
    name: str
    code: str
    color_code: str


class RepairGarageLocation(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None


class RepairPlanDetailItem(BaseModel):
    name: str
    item: RepairItem
    type: RepairType
    garage_price: float
    suggested_price: float
    discount_percentage: float


class RepairPlanApprovalRequest(BaseModel):
    file_number: str
    vehicle_name: str
    repair_garage_location: RepairGarageLocation
    inspection_date: Optional[str] = None
    approval_deadline: Optional[str] = None
    status: Status
    label: Label
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
    file_name: str
    contract_number: str
    vehicle_info: str
    repair_garage_location: RepairGarageLocation
    inspection_date: str
    approval_deadline: str
    owner_name: str
    owner_phone: str
    status: Status
    approval_history: List[ApprovalHistory]
    repair_plan_details: List[RepairPlanDetailItem]
    amount_subtotal: float
    amount_discount: float
    amount_untaxed_total: float


class RepairPlanDetailResponse(BaseModel):
    # data: RepairPlanAwaitingDetail
    data: dict


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
