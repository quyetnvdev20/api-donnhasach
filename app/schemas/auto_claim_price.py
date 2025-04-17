from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum


class PriceType(str, Enum):
    PAINT = "paint"
    LABOR = "labor"
    REPLACEMENT = "parts"

class CarObject(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    
class PartObject(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    
class ResponsePartObject(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    
class GarageObject(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None

class ProvinceObject(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None

class AutoClaimPriceRequest(BaseModel):
    car: CarObject
    part: PartObject
    type: PriceType
    province: ProvinceObject
    garage: GarageObject

class AutoClaimPriceResponse(BaseModel):
    pricelist: Optional[str] = None
    price: Optional[float] = None
    parts: Optional[ResponsePartObject] = None