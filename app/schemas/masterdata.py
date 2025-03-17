from pydantic import BaseModel
from typing import List, Optional, Dict, Any



class GarageItem(BaseModel):
    id: int
    name: str
    street: Optional[str] = None
    distance: float = None
    travel_time_minutes: int = None


class GarageListResponse(BaseModel):
    data: List[GarageItem] = []


class BranchItem(BaseModel):
    id: int
    name: str
    code: Optional[str] = None


class BranchListResponse(BaseModel):
    data: List[BranchItem] = []

class AppraiserItem(BaseModel):
    id: int
    name: str


class AppraiserListResponse(BaseModel):
    data: List[AppraiserItem] = []
