from fastapi import APIRouter, Depends, HTTPException, status, Body, Query, Header
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Annotated

from app.utils import shorten_url
from ...deps import get_current_user
from ....config import settings, odoo
from ....database import get_db
from ....schemas.remote_inspection import CreateInvitationRequest, CreateInvitationResponse, ValidateInvitationRequest, \
    ValidateInvitationResponse, ActionInvitationResponse, DoneInvitationRequest, CancelInvitationRequest, \
    SaveImageRequest, SaveImageResponse, CancelInvitationResponse
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
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))


async def get_keycloak_access_token(user_id):
    """Get access token asynchronously from Tasco API.
    
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
                session_state = data.get('session_state')
                if not access_token:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Invalid response from authentication service"
                    )
                return access_token, session_state

    except aiohttp.ClientError as e:
        logger.error(f"Network error while getting access token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to authentication service"
        )


async def delete_keycloak_access_token(user_id: str, session_state:str) -> bool:
    """Delete access token asynchronously from Tasco API.

    Args:
        user_id (str): User ID to revoke access token
        session_state (str): Access token to revoke

    Returns:
        bool: True if token was successfully revoked

    Raises:
        HTTPException: If there is any error during token deletion
    """
    logger.info(f"Attempting to delete access token for user {user_id}")

    # Validate input parameters
    if not user_id or not session_state:
        logger.error("Missing required parameters: user_id or session_state")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id and session_state are required"
        )

    # Get environment variables
    api_url = os.getenv('INSURANCE_API_URL')
    api_key = os.getenv('KEYCLOAK_API_KEY')

    if not api_url or not api_key:
        logger.error("Missing required environment variables: INSURANCE_API_URL or KEYCLOAK_API_KEY")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error"
        )

    url = f"{api_url}/super-auth/user/access-token"
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    params = {
        'user_id': user_id,
        'session_id': session_state
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, params=params, headers=headers) as response:
                if response.status != 200:
                    error_msg = f"Failed to delete token. Status: {response.status}"
                    logger.error(f"{error_msg} for user {user_id}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=error_msg
                    )

                data = await response.json()
                success = data.get('success', False)

                if not success:
                    error_msg = f"Failed to delete token. Response: {data}"
                    logger.error(f"{error_msg} for user {user_id}")
                    return False

                logger.info(f"Successfully deleted access token for user {user_id}")
                return True

    except aiohttp.ClientError as e:
        error_msg = f"Network error while deleting access token: {str(e)}"
        logger.error(f"{error_msg} for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )
    except Exception as e:
        error_msg = f"Unexpected error while deleting token: {str(e)}"
        logger.error(f"{error_msg} for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
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

    query = """
        select id, invitation_code, expire_at, deeplink
        from insurance_claim_remote_inspection 
        where appraisal_detail_id = %(assessment_id)s 
        and status = 'new' 
        and expire_at >= now()
        limit 1
    """
    params = {'assessment_id': create_invitation_vals.assessment_id}
    results = await PostgresDB.execute_query(query, params)
    if results and results[0]:
        res = results[0]
        vals = {
            "invitation_code": res.get('invitation_code'),
            "invitation_id": res.get('id'),
            "expire_at": res.get('expire_at').strftime("%Y-%m-%d %H:%M:%S"),
            "deeplink": res.get('deeplink') or ''
        }
        return CreateInvitationResponse(data=vals, status="Success")

    invitation_code, cache_key = await generate_unique_invitation_code(redis_client_instance)

    expire_at = datetime.now(tz=ZoneInfo("UTC")) + timedelta(days=1)
    expire_at_str = expire_at.strftime("%Y-%m-%d %H:%M:%S")
    # deeplink = f"{settings.DEEPLINK_APP}?invitation_code={invitation_code}"
    deeplink = f"{settings.DEEPLINK_APP}/invitation_code"
    shorten_deeplink = await shorten_url.generate_shorten_url(deeplink)

    odoo_vals = {
        'name': create_invitation_vals.expert_name,
        'phone': create_invitation_vals.expert_phone,
        'invitation_code': invitation_code,
        'expire_at': expire_at_str,
        'appraisal_detail_id': create_invitation_vals.assessment_id,
        'deeplink': shorten_deeplink,
    }

    response = await odoo.create_method(
        model='insurance.claim.remote.inspection',
        vals=odoo_vals,
        token=current_user.odoo_token,
    )

    if response:
        access_token, session_state = await get_keycloak_access_token(current_user.uid)

        # Lưu vào Redis dưới dạng JSON
        cache_data = {
            'access_token': access_token,
            'session_state': session_state,
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
            "invitation_id": response.get('id'),
            "expire_at": local_expire_at.strftime("%Y-%m-%d %H:%M:%S"),
            "deeplink": shorten_deeplink
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
            detail="Mã mời không hợp lệ hoặc đã hết hạn"
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
        headers: Annotated[CommonHeaders, Header()],
        save_image_vals: SaveImageRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    if not save_image_vals.invitation_id and not save_image_vals.assessment_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thiếu thông tin bắt buộc: invitation_id hoặc assessment_id"
        )

    if save_image_vals.invitation_id:
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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response.get("message"))
    else:
        vals_items = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "type_document_id": int(settings.APPRAISAL_IMAGE_TYPE_DOCUMENT),
            "type": "photo",
            "attachment_ids": [(0, 0, {
                "date_upload": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "latitude": headers.latitude if headers.latitude else None,
                "longitude": headers.longitude if headers.longitude else None,
                "link": save_image_vals.face_image_url + '?image_process=resize,w_100,h_100',
                "link_preview": save_image_vals.face_image_url,
                "location": '',
                "note": ''
            })]
        }
        vals = {
            'appraisal_attachment_ids': [(0, 0, vals_items)]
        }

        response = await odoo.update_method(
            model='insurance.claim.appraisal.detail',
            record_id=save_image_vals.assessment_id,
            vals=vals,
            token=current_user.odoo_token,
        )
        if response:
            return SaveImageResponse(id=save_image_vals.assessment_id)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response.get("message"))


@router.post("/done",
             response_model=ActionInvitationResponse)
async def done_remote_inspection(
        headers: Annotated[CommonHeaders, Header()],
        done_invitation_vals: DoneInvitationRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    query = """
            select id from insurance_claim_remote_inspection 
            where invitation_code = %(invitation_code)s 
            and status = 'new' 
            and appraisal_detail_id = %(assessment_id)s
            limit 1
        """
    params = {'invitation_code': headers.invitationCode, 'assessment_id': done_invitation_vals.assessment_id}
    results = await PostgresDB.execute_query(query, params)
    if not results or not results[0]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mã mời không khả dụng để thực hiện hành động này."
        )

    response = await odoo.call_method_not_record(
        model='insurance.claim.remote.inspection',
        method='action_done_remote_inspection_api',
        token=current_user.odoo_token,
        kwargs={'invitation_id': results[0].get('id')}
    )
    if response:
        return ActionInvitationResponse(data={'id': done_invitation_vals.assessment_id})
    else:
        raise Exception(response.get("message"))


@router.post("/cancel",
             response_model=CancelInvitationResponse)
async def cancel_remote_inspection(
        cancel_invitation_vals: CancelInvitationRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    # Kiểm tra invitation trong database
    query = """
        select invitation_code from insurance_claim_remote_inspection 
        where id = %(id)s and status = 'new'
    """
    params = {'id': cancel_invitation_vals.id}
    results = await PostgresDB.execute_query(query, params)
    if not results or not results[0]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mã mời không khả dụng để thực hiện hành động này"
        )

    invitation_code = results[0].get('invitation_code')
    cache_key = get_cache_key(invitation_code)

    try:
        # Cập nhật status trong Odoo
        vals = {'status': 'cancel'}
        response = await odoo.update_method(
            model='insurance.claim.remote.inspection',
            record_id=cancel_invitation_vals.id,
            vals=vals,
            token=current_user.odoo_token,
        )
        if not response:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=response.get("message", "Failed to cancel invitation in Odoo")
            )

        # Xử lý Redis cache và Keycloak token
        if await redis_client_instance.exists(cache_key):
            cached_data = await redis_client_instance.get(cache_key)
            session_state = cached_data.get('session_state')

            if session_state:
                # Xóa token trong Keycloak
                status_delete = await delete_keycloak_access_token(current_user.uid, session_state)
                if status_delete:
                    # Xóa cache trong Redis
                    await redis_client_instance.delete(cache_key)

        return CancelInvitationResponse(data={'id': cancel_invitation_vals.id})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error canceling invitation {cancel_invitation_vals.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while canceling invitation"
        )
