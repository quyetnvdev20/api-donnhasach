from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# Models for Doc Vision
class DocVisionRequest(BaseModel):
    image_url: str
    
class DocVisionResponse(BaseModel):
    type: str
    name: str
    type_document_id: int
    content: dict = {}
    image_url: str
