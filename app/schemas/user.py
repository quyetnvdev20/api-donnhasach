from typing import List, Optional
from pydantic import BaseModel


class UserPermission(BaseModel):
    id: Optional[int] = None
    code: str

class UserObject(BaseModel):
    access_token: str
    sub: str
    username: str
    erp_id: int
    odoo_token: str
    uid: str
    perms: Optional[List[UserPermission]] = None

    def get(self, key: str, default=None):
        """Allow dictionary-style access with .get() method"""
        if hasattr(self, key):
            return getattr(self, key)
        return default
    
    def __getitem__(self, key: str):
        """Allow dictionary-style access with [] operator"""
        return self.get(key)
    
    def has_permission(self, permission: str) -> bool:
        return any(perm.code == permission for perm in self.perms)