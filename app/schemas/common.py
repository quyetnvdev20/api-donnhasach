from pydantic import BaseModel
from zoneinfo import ZoneInfo


class CommonHeaders(BaseModel):
    time_zone: ZoneInfo = ZoneInfo("Asia/Ho_Chi_Minh")
