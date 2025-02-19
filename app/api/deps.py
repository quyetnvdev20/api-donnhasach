from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..config import settings
import requests
from typing import Optional
import json

security = HTTPBearer()

def get_token_introspection_url():
    return f"{settings.KEYCLOAK_HOST}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token/introspect"

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Validate token bằng Keycloak introspection endpoint
    """
    token = credentials.credentials
    introspection_url = get_token_introspection_url()
    
    # Gọi Keycloak introspection endpoint
    response = requests.post(
        introspection_url,
        data={
            'token': token,
            'client_id': settings.KEYCLOAK_CLIENT_ID,
            'client_secret': settings.KEYCLOAK_CLIENT_SECRET,
        }
    )
    
    if not response.ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = response.json()
    
    # Kiểm tra token có active không
    if not token_data.get("active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not active",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data 