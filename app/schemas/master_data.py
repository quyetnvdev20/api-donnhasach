from pydantic import BaseModel
from typing import List, Optional, Dict, Any



class GarageItem(BaseModel):
    id: int
    name: str
    street: Optional[str] = None


class GarageListResponse(BaseModel):
    data: List[GarageItem] = []
