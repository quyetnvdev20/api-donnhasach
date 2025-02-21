from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from ..config import settings
import requests
from typing import Optional

# Thay thế HTTPBearer bằng APIKeyHeader
api_key_header = APIKeyHeader(name="Authorization", auto_error=True)

def get_token_introspection_url():
    return f"{settings.KEYCLOAK_HOST}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token/introspect"

async def get_current_user(token: str = Depends(api_key_header)) -> dict:
    """
    Validate token bằng Keycloak introspection endpoint
    """
    # Không cần kiểm tra prefix "Bearer" nữa
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