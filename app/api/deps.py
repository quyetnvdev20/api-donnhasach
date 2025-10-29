import httpx
from app.schemas.user import UserObject
from app.utils.redis_client import redis_client as redis_client_instance
from app.utils.erp_db import PostgresDB
from fastapi.security import APIKeyHeader
from ..config import settings, odoo
import logging
from fastapi import APIRouter, Request, Header, HTTPException, status, Depends
import jwt

# Thay thế HTTPBearer bằng APIKeyHeader
api_key_header = APIKeyHeader(name="Authorization", auto_error=True)
logger = logging.getLogger(__name__)


def get_token_key(token):
    return "{}::{}".format(settings.TOKEN_PREFIX, token)


async def parse_token(token: str):
    if not await redis_client_instance.exists(get_token_key(token)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token exists",
        )
    return jwt.decode(token, settings.TOKEN_PREFIX, algorithms=["HS256"])



async def get_current_user(token: str = Depends(api_key_header)) -> UserObject:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    odoo_user = await parse_token(token)
    user_data = {
        'odoo_token': odoo_user.get('token'),
        'uid': odoo_user.get('uid'),
        'partner_id': odoo_user.get('partner_id')
    }

    return UserObject(**user_data)



async def verify_signature(
        request: Request,
):
    ## Header
    headers = request.headers
    logger.info(f"header: {headers}")
    logger.info(f"request: {request}")
    authorization = headers.get("aukey")
    PORTAL_KEY = settings.PORTAL_KEY

    logger.info(f"Authorization: {authorization}")
    logger.info(f"ARE_SOF_SECRET_KEY: {PORTAL_KEY}")

    if authorization != PORTAL_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
    return True

async def get_value_fields_selection(model, fields):
    result = await odoo.call_method_not_record(
        model='res.users',
        method='get_select_value_by_model',
        token=settings.ODOO_TOKEN,
        kwargs={'model': model, 'fields': fields},
    )
    return result
