from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ConnectRequest(BaseModel):
    code: str
    name: str
    db_host : str
    db_port : str
    db_user : str
    db_password : str
    db_name : str
    backend_host : str
    backend_port : str
class ConnectResponse(BaseModel):
    id: str