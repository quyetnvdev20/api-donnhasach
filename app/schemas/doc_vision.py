from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# Models for Doc Vision
class DocVisionRequest(BaseModel):
    list_image_url: List[str]  = []

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
    name: Optional[str] = None
    images: Optional[List[ImageDocument]] = None
    
class DocVisionResponse(BaseModel):
    name_driver: Optional[str] = None
    gplx_no: Optional[str] = None
    gplx_level: Optional[str] = None
    gplx_effect_date: Optional[str] = None
    gplx_expired_date: Optional[str] = None
    registry_no: Optional[str] = None
    registry_date: Optional[str] = None
    registry_expired_date: Optional[str] = None
    documents: List[Document]

