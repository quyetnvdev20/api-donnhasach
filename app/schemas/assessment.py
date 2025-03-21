from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# Models for Assessment List
class AssessmentListItem(BaseModel):
    id: int
    name: str
    license_plate: str = None
    vehicle: Optional[str]
    customer_name: Optional[str]
    assessment_address: Optional[str]
    gara_address: Optional[str]
    # travel_time_minutes: Optional[int]
    location: Optional[str]
    current_distance: float
    notification_time: Optional[str]
    complete_time: Optional[str]
    urgency_level: bool
    assessment_progress: int
    note: Optional[str] = None
    status: Optional[str]
    status_color: Optional[str] = "#212121"


class AssessmentStatus(Enum):
    WAIT = 'wait'
    DONE = 'done'
    CANCEL = 'cancel'


# Models for Assessment Detail
class TaskStatus(BaseModel):
    bg_color: str
    name: str


class Task(BaseModel):
    seq: int
    name: str
    path: str
    desc: str
    icon: str
    status: TaskStatus = None

class UserRequest(BaseModel):
    name: str
    phone: str
    datetime_request: str

class RemoteInspection(BaseModel):
    name: str
    phone: str
    invitation_code: str
    status: str
    label: str
    message: Optional[str] = None

class State(BaseModel):
    name: str
    code: str
    color_code: str

class AssessmentDetail(BaseModel):
    case_number: str
    status: str
    state : State
    license_plate: Optional[str] = None
    vehicle: Optional[str] = None
    location: Optional[str] = None
    assessment_address: Optional[str] = None
    owner_name: Optional[str] = None
    phone_number: Optional[str] = None
    accident_date: Optional[str] = None
    incident_desc: Optional[str] = None
    appraisal_date: Optional[str] = None
    complete_time: Optional[str] = None
    damage_desc: Optional[str] = None
    assessment_progress: int = None
    note: Optional[str] = None
    assigned_to: Optional[str] = None
    tasks: List[Task]
    status_color: Optional[str] = "#212121"
    claim_profile_id: Optional[int] = None
    insur_claim_id: Optional[int] = None
    user_request: Optional[UserRequest] = None
    list_remote_inspection: Optional[List[RemoteInspection]] = None


# Models for Vehicle Detail Assessment
class DamageInfo(BaseModel):
    id: int
    name: str


# Schema for image information
class ImageInfo(BaseModel):
    id: Optional[int] = None
    link: str = None
    location: Optional[str] = None
    lat: Optional[float] = None
    long: Optional[float] = None
    date: Optional[str] = None
    
    def dict(self, *args, **kwargs):
        """Custom dict method to ensure proper serialization"""
        result = super().dict(*args, **kwargs)
        # Ensure all values are JSON serializable
        for key, value in result.items():
            if value is None:
                continue
            if not isinstance(value, (str, int, float, bool, list, dict)):
                result[key] = str(value)
        return result
    
    class Config:
        from_attributes = True
        json_encoders = {
            # Add custom encoders if needed
        }


# Schema for category ID
class Category(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None


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
    id: Optional[int] = None
    category_id: Category
    state: Status
    solution: Solution = Solution(code='repair', name='Sửa chữa')
    listImageRemove: List[int] = None
    images: List[ImageInfo] = None


class VehicleDetailAssessment(BaseModel):
    items: List[AssessmentItem]

class DocumentType(BaseModel):
    id: int
    name: str
    code: str

# Models for Document Collection
class ImageDocument(BaseModel):
    date: Optional[str] = None
    description: Optional[str] = None
    id: Optional[int] = None
    lat: Optional[float] = None
    long: Optional[float] = None
    location: Optional[str] = None
    link: Optional[str] = None

class Document(BaseModel):
    type: str = ""
    type_document_id: Optional[int] = None
    listImageRemove: Optional[List[int]] = None
    name: Optional[str] = None
    desc: Optional[str] = None
    images: Optional[List[ImageDocument]] = None
    id: Optional[int] = None


class SceneAttachment(BaseModel):
    documents: List[Document]

class SceneAttachmentResponse(BaseModel):
    assessment_id: int = ""
    status: str = ""

class DocumentCollection(BaseModel):
    # Thông tin từ get_data_collect_document
    id: Optional[int] = None
    state: Optional[str] = None
    name_driver: Optional[str] = None
    phone_driver: Optional[str] = None
    cccd: Optional[str] = None
    gender_driver: Optional[str] = None
    gplx_no: Optional[str] = None
    gplx_level: Optional[str] = None
    gplx_effect_date: Optional[str] = None
    gplx_expired_date: Optional[str] = None
    registry_no: Optional[str] = None
    registry_date: Optional[str] = None
    registry_expired_date: Optional[str] = None
    user_id: Optional[int] = None
    state_assign: Optional[str] = None
    appraisal_ho_id: Optional[int] = None
    object: Optional[str] = None
    documents: List[Document]


# Models for Accident Notification and Assessment Report
class DocumentUpload(BaseModel):
    # type_document_id: int
    # type: str
    scan_url: List[ImageInfo]
    list_image_remove: List[int] = None


class DocumentResponse(BaseModel):
    preview_url: str = ""
    scan_url: List[ImageInfo] = None


class UpdateDocumentResponse(BaseModel):
    status: str = ""

class UpdateAssessmentItemResponse(BaseModel):
    assessment_id: str = ""
    status: str = ""

class OCRCategory(BaseModel):
    id: Optional[int] = None
    code: Optional[str] = None
    name: Optional[str] = None

class CategoryType(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    color_code: Optional[str] = None

class OCRQuoteItem(BaseModel):
    name: str = ""
    quantity: int = 1
    garage_price: float = 0
    item: OCRCategory
    discount_percentage: float = 0
    type: CategoryType = None
class OCRQuoteResponse(BaseModel):
    url_cvs: str
    data: List[OCRQuoteItem] = []

class AssignAppraisalRequest(BaseModel):
    user_id: int
    branch_id: int


class AssignAppraisalResponse(BaseModel):
    success: bool
    message: str
