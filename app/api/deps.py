import httpx
from app.schemas.user import UserObject
from app.utils.redis_client import redis_client as redis_client_instance
from app.utils.erp_db import PostgresDB
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from ..config import settings, odoo
import logging


# Thay thế HTTPBearer bằng APIKeyHeader
api_key_header = APIKeyHeader(name="Authorization", auto_error=True)
logger = logging.getLogger(__name__)

def get_token_introspection_url():
    return f"{settings.KEYCLOAK_HOST}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token/introspect"

async def get_current_user(token: str = Depends(api_key_header)) -> UserObject:
    """
    Validate token bằng Keycloak introspection endpoint
    """
    # Không cần kiểm tra prefix "Bearer" nữa
    introspection_url = get_token_introspection_url()
    
    # Gọi Keycloak introspection endpoint
    async with httpx.AsyncClient() as client:
        response = await client.post(
            introspection_url,
            data={
                'token': token,
                'client_id': settings.KEYCLOAK_CLIENT_ID,
                'client_secret': settings.KEYCLOAK_CLIENT_SECRET,
            },
            timeout=10
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials", 
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_data = response.json()
        logger.info(f"Token data: {token_data}")
    
    # Kiểm tra token có active không
    if not token_data.get("active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not active",
            headers={"WWW-Authenticate": "Bearer"},
        )
    odoo_user = await ensure_odoo_user(token_data.get("sub"))
    user_perms = await get_user_permission(odoo_user.get("token"))
    token_data.update({
        **odoo_user,
        'access_token': token,
        'erp_id': odoo_user.get('id'),
        'perms': user_perms,
        'odoo_token': odoo_user.get('token'),
        'uid': token_data.get('sub')
    })

    user_object = UserObject(**token_data)

    return user_object

async def ensure_odoo_user(sub: str) -> dict:
    cache_key = f"odoo_user_{sub}"
    if await redis_client_instance.exists(cache_key):
        cached_user = await redis_client_instance.get(cache_key)
        return cached_user
    else:
        user = await odoo.search_method(
            model='res.users',
            domain=[
            ('oauth_provider_id', '=', settings.ODOO_OAUTH_PROVIDER_ID),
            ('oauth_uid', '=', sub),
            ('active', '=', True)
        ],
        fields=['token', 'name'],
        limit=1,
        offset=0
    )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User is not exist",
            )
        if 'success' in user:
            user = user['success'][0]
        else:
            user = user[0]
        # Cache to redis
        await redis_client_instance.set(cache_key, user)
        return user

async def get_user_permission(token: str) -> dict:
    cache_key = f"user_permission_{token}"
    if await redis_client_instance.exists(cache_key):
        cached_permission = await redis_client_instance.get(cache_key)
        return cached_permission
    else:
        query = """
            select rg.id,
                    rg.comment #>> '{en_US}' as code
        from res_groups rg,
                res_groups_users_rel rgur
        left join res_users ru on ru.id = rgur.uid
        where rg.id = rgur.gid
            and ru.token = $1
            and comment #>> '{en_US}' like ('perm%')
    """
        result = await PostgresDB.execute_query(query, [token])
        if result:
            user_perms = [
                {
                    "id": perm['id'],
                    "code": perm['code']
                }
                for perm in result
            ]
            # Cache to redis
            await redis_client_instance.set(cache_key, user_perms)
            return user_perms
        else:
            return None
