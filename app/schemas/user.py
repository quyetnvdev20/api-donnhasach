from typing import List, Optional
from pydantic import BaseModel


class UserPermission(BaseModel):
    id: Optional[int] = None
    code: str

class UserObject(BaseModel):
    odoo_token: str
    uid: int
    partner_id: int

    def get(self, key: str, default=None):
        """Allow dictionary-style access with .get() method"""
        if hasattr(self, key):
            return getattr(self, key)
        return default
    
    def __getitem__(self, key: str):
        """Allow dictionary-style access with [] operator"""
        return self.get(key)