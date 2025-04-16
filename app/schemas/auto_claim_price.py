from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum


class PriceType(str, Enum):
    PAINT = "paint"
    LABOR = "labor"
    REPLACEMENT = "parts"

class CarObject(BaseModel):
    brand: str
    model: str
    
class PartObject(BaseModel):
    code: str
    name: str
    
class ResponsePartObject(BaseModel):
    code: str | None = None
    name: str | None = None
    
class GarageObject(BaseModel):
    code: str
    name: str

class ProvinceObject(BaseModel):
    code: str
    name: str

class AutoClaimPriceRequest(BaseModel):
    car: CarObject
    part: PartObject
    type: PriceType
    province: ProvinceObject
    garage: GarageObject

class AutoClaimPriceResponse(BaseModel):
    pricelist: str | None = None
    price: float | None = None
    parts: ResponsePartObject | None = None