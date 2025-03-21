from fastapi import APIRouter, Depends, HTTPException, status, Body, Query, Header
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Annotated
from ...deps import get_current_user
from ....config import settings, odoo
from ....database import get_db
from ....schemas.remote_inspection import CreateInvitationRequest, CreateInvitationResponse, ValidateInvitationRequest, \
    ValidateInvitationResponse, ActionInvitationResponse, DoneInvitationRequest, DeleteInvitationRequest, SaveImageRequest, SaveImageResponse
import logging
import asyncio
from ....utils.erp_db import PostgresDB
import random
import string
from datetime import datetime, timedelta
from ....schemas.common import CommonHeaders
from zoneinfo import ZoneInfo
import aiohttp
import os
from app.utils.redis_client import redis_client as redis_client_instance
import json


logger = logging.getLogger(__name__)

router = APIRouter()


def generate_invitation_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=3))


async def get_and_save_access_token(user_id):
    """Get and save access token asynchronously from Tasco API.
    
    Args:
        user_id: User ID to get access token
        
    Returns:
        str: Access token
        
    Raises:
        HTTPException: If API call fails
    """
    try:
        url = f"{os.getenv('INSURANCE_API_URL')}/super-auth/user/access-token?user_id={user_id}"
        headers = {
            'X-API-KEY': f"{os.getenv('KEYCLOAK_API_KEY')}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to get access token for user {user_id}. Status: {response.status}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Failed to get access token from authentication service"
                    )
                    
                data = await response.json()
                access_token = data.get('access_token')
                if not access_token:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Invalid response from authentication service"
                    )
                return access_token
                
    except aiohttp.ClientError as e:
        logger.error(f"Network error while getting access token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to authentication service"
        )

def get_cache_key(code):
    return f"remote_inspection_{code}"


async def generate_unique_invitation_code(redis_client, max_attempts: int = 10):
    """Generate a unique invitation code that doesn't exist in Redis.
    
    Args:
        redis_client: Redis client instance
        max_attempts: Maximum number of attempts to generate unique code. Defaults to 10.
        
    Returns:
        tuple: (invitation_code, cache_key)
        
    Raises:
        HTTPException: If unable to generate unique code after max attempts
    """
    attempts = 0
    while attempts < max_attempts:
        invitation_code = generate_invitation_code()
        cache_key = get_cache_key(invitation_code)
        exists = await redis_client.exists(cache_key)
        if not exists:
            return invitation_code, cache_key
        attempts += 1
    
    logger.error(f"Failed to generate unique invitation code after {max_attempts} attempts")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Unable to generate unique invitation code after {max_attempts} attempts"
    )


@router.post("/create-invitation",
             response_model=CreateInvitationResponse)
async def create_invitation(
        headers: Annotated[CommonHeaders, Header()],
        create_invitation_vals: CreateInvitationRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    invitation_code, cache_key = await generate_unique_invitation_code(redis_client_instance)
    
    expire_at = datetime.now(tz=ZoneInfo("UTC")) + timedelta(days=1)
    expire_at_str = expire_at.strftime("%Y-%m-%d %H:%M:%S")

    odoo_vals = {
        'name': create_invitation_vals.expert_name,
        'phone': create_invitation_vals.expert_phone,
        'invitation_code': invitation_code,
        'expire_at': expire_at_str,
        'appraisal_detail_id': create_invitation_vals.assessment_id,
    }

    response = await odoo.create_method(
        model='insurance.claim.remote.inspection',
        vals=odoo_vals,
        token=current_user.odoo_token,
    )

    if response:
        access_token = await get_and_save_access_token(current_user.uid)

        # Lưu vào Redis dưới dạng JSON
        cache_data = {
            'access_token': access_token,
            'assessment_id': create_invitation_vals.assessment_id,
            'odoo_token': current_user.odoo_token,
            'res_id': response.get('id')
        }

        await redis_client_instance.set(
            cache_key,
            json.dumps(cache_data),
            expiry=86400  # 24 giờ in seconds
        )
        local_expire_at = expire_at.astimezone(headers.time_zone)
        vals = {
            "invitation_code": invitation_code,
            "expire_at": local_expire_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        return CreateInvitationResponse(data=vals, status="Success")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create invitation")


@router.post("/validate-invitation",
             response_model=ValidateInvitationResponse)
async def validate_invitation(
        validate_invitation_vals: ValidateInvitationRequest = Body(...),
        db: Session = Depends(get_db)
):
    """Validate invitation code and return access information.
    
    Args:
        validate_invitation_vals: Request containing invitation code
        db: Database session
        
    Returns:
        ValidateInvitationResponse: Access information if valid
        
    Raises:
        HTTPException: If invitation code is invalid or expired
    """
    cache_key = get_cache_key(validate_invitation_vals.invitation_code)

    # Kiểm tra xem invitation code có tồn tại trong cache không
    if not await redis_client_instance.exists(cache_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invitation code"
        )

    # Lấy cached data
    cached_data = await redis_client_instance.get(cache_key)

    # Kiểm tra các trường bắt buộc trong cached data
    if not all(key in cached_data for key in ['access_token', 'assessment_id']):
        logger.error(f"Missing required fields in cached data for key: {cache_key}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid invitation data format"
        )

    vals = {
        "access_token": cached_data['access_token'],
        "refresh_token": None,  # Có thể thêm logic refresh token nếu cần
        "expires_in": 86400,  # 24 hours in seconds
        "assessment_id": cached_data['assessment_id'],
        "invitation_id": cached_data['res_id'],
    }
    return ValidateInvitationResponse(data=vals)


@router.post("/save-face-image",
             response_model=SaveImageResponse)
async def save_face_image(
        save_image_vals: SaveImageRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    odoo_vals = {
        'face_image_url': save_image_vals.face_image_url,
        # 'capture_time': validate_invitation_vals.capture_time
    }

    response = await odoo.update_method(
        model='insurance.claim.remote.inspection',
        record_id=save_image_vals.invitation_id,
        vals=odoo_vals,
        token=current_user.odoo_token,
    )
    if response:
        return SaveImageResponse(id=save_image_vals.invitation_id)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to save face image")


@router.post("/done",
             response_model=ActionInvitationResponse)
async def done_remote_inspection(
        done_invitation_vals: DoneInvitationRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    assessment_id = done_invitation_vals.assessment_id
    response = await odoo.call_method_not_record(
        model='insurance.claim.remote.inspection',
        method='action_done_remote_inspection_api',
        token=current_user.odoo_token,
        kwargs={'invitation_id': done_invitation_vals.invitation_id}
    )
    if response:
        return ActionInvitationResponse(data={'id': assessment_id})
    else:
        raise Exception(response.get("message"))


@router.post("/cancel",
             response_model=ActionInvitationResponse)
async def cancel_remote_inspection(
        delete_invitation_vals: DeleteInvitationRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    vals = {
        "id": 5922
    }
    return ActionInvitationResponse(data=vals)
