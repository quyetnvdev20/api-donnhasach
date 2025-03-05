from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# Models for Assessment List
class AssessmentListItem(BaseModel):
    name: str
    license_plate: str
    vehicle: Optional[str]
    customer_name: Optional[str]
    assessment_address: Optional[str]
    current_distance: float
    notification_time: Optional[str]
    complete_time: Optional[str]
    urgency_level: bool
    assessment_progress: int
    note: Optional[str] = None
    status: Optional[str]
    status_color: Optional[str] = "#212121"


# Models for Assessment Detail
class TaskStatus(BaseModel):
    bg_color: str
    name: str


class Task(BaseModel):
    seq: int
    id: Optional[int] = None
    name: str
    path: str
    desc: str
    icon: str
    status: TaskStatus


class AssessmentDetail(BaseModel):
    case_number: str
    vehicle: str
    location: str
    owner_name: str
    phone_number: str
    accident_date: str
    incident_desc: str
    damage_desc: str
    assessment_progress: int
    note: Optional[str] = None
    tasks: List[Task]


# Models for Vehicle Detail Assessment
class DamageInfo(BaseModel):
    id: int
    name: str


# Schema for image information
class ImageInfo(BaseModel):
    id: int
    link: str
    location: Optional[str] = None
    lat: Optional[str] = None
    long: Optional[str] = None
    date: Optional[str] = None


# Schema for category ID
class CategoryId(BaseModel):
    id: int
    name: str


# Schema for status
class Status(BaseModel):
    id: int
    name: str


# Schema for solution
class Solution(BaseModel):
    code: Optional[str] = None
    name: str


# Schema for assessment item
class AssessmentItem(BaseModel):
    id: int
    category_id: CategoryId
    status: Status
    solution: Solution
    images: List[ImageInfo]


class VehicleDetailAssessment(BaseModel):
    assessment_id: int
    items: List[AssessmentItem]


# Models for Document Collection
class Document(BaseModel):
    type_document_id: int
    type: str = ""
    name: str = ""
    desc: str = ""
    place_holder: Optional[str] = ""
    images: List[ImageInfo]


class DocumentCollection(BaseModel):
    name_driver: Optional[str] = None
    phone_driver: Optional[str] = None
    cccd: Optional[str] = None
    gender_driver: Optional[str] = None
    gplx_effect_date: Optional[str] = None
    gplx_expired_date: Optional[str] = None
    gplx_level: Optional[str] = None
    gplx_no: Optional[str] = None
    registry_date: Optional[str] = None
    registry_expired_date: Optional[str] = None
    registry_no: Optional[str] = None
    documents: List[Document]


# Models for Accident Notification and Assessment Report
class DocumentUpload(BaseModel):
    scan_url: List[ImageInfo]


class DocumentResponse(BaseModel):
    preview_url: str = ""
    scan_url: List[ImageInfo]
