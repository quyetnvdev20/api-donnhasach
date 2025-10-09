from pydantic import BaseModel, Field
from typing import Optional
from zoneinfo import ZoneInfo


class CommonHeaderPortal(BaseModel):
    x_portal_key: str = None
