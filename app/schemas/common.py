from pydantic import BaseModel, Field
from typing import Optional
from zoneinfo import ZoneInfo


class CommonHeaders(BaseModel):
    time_zone: ZoneInfo = ZoneInfo("Asia/Ho_Chi_Minh")
    latitude: float = None
    longitude: float = None
    invitation_code: str = None
