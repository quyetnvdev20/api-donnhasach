from fastapi import APIRouter, Depends, HTTPException, status, Body, Query, Header
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Annotated
from ...deps import get_current_user
from ....config import settings, odoo
from ....database import get_db
from ....schemas.remote_inspection import CreateInvitationRequest, CreateInvitationResponse, ValidateInvitationRequest, \
    ValidateInvitationResponse, ActionInvitationResponse, ActionInvitationRequest
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


logger = logging.getLogger(__name__)

router = APIRouter()


def generate_invitation_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=3))


async def get_and_save_access_token(user_id):
    """Get and save access token asynchronously from Tasco API.
    """

    url = f"{os.getenv('INSURANCE_API_URL')}/super-auth/user/access-token?user_id={user_id}"

    headers = {
        'X-API-KEY': f"{os.getenv('KEYCLOAK_API_KEY')}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            access_token = data.get('access_token')
            return access_token

def get_cache_key(code):
    return f"remote_inspection_{code}"


@router.post("/create-invitation",
             response_model=CreateInvitationResponse)
async def create_invitation(
        headers: Annotated[CommonHeaders, Header()],
        create_invitation_vals: CreateInvitationRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    invitation_code = generate_invitation_code()
    expire_at = datetime.now(tz=ZoneInfo("UTC")) + timedelta(days=1)
    expire_at_str = expire_at.strftime("%Y-%m-%d %H:%M:%S")

    cache_key = get_cache_key(invitation_code)
    access_token = await get_and_save_access_token(current_user.uid)
    vals = {
        'access_token': access_token,
        'assessment_id': create_invitation_vals.assessment_id
    }
    await redis_client_instance.set(cache_key, str(vals))

    odoo_vals = {
        'remote_inspection_ids': [(0, 0, {
            'name': create_invitation_vals.expert_name,
            'phone': create_invitation_vals.expert_phone,
            'invitation_code': invitation_code,
            'expire_at': expire_at_str,
        })]
    }

    response = await odoo.update_method(
        model='insurance.claim.appraisal.detail',
        record_id=create_invitation_vals.assessment_id,
        vals=odoo_vals,
        token=current_user.odoo_token,
    )

    if response:
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
    vals = {
        "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICI3d1pHZmJDWlQxUGg1YVNzSXF1NkN4TWpIa3NmZE5Qa0FLb3doLUlnY0FNIn0.eyJleHAiOjE3NzM5MDg4MTcsImlhdCI6MTc0MjM3MjgxNywianRpIjoiNzYwYmNhM2YtZTc0MC00YWIzLWE0NjAtMjEzMjYzZDk4ZTM3IiwiaXNzIjoiaHR0cHM6Ly9kZXYtc3NvLmJhb2hpZW10YXNjby52bi9yZWFsbXMvbWFzdGVyIiwiYXVkIjoiYWNjb3VudCIsInN1YiI6IjQ0YTBkNGY3LTY3NDUtNDY4MS1hNTExLTZkY2JmNTg3MWQ5YyIsInR5cCI6IkJlYXJlciIsImF6cCI6InRhc2NvLWluc3VyYW5jZS1kZXYiLCJzZXNzaW9uX3N0YXRlIjoiNzFiYWM5MTAtNDdjNy00ZGQzLTg5Y2QtNDM5ZmMyNDc1NWNhIiwiYWNyIjoiMSIsImFsbG93ZWQtb3JpZ2lucyI6WyIiLCIqIl0sInJlYWxtX2FjY2VzcyI6eyJyb2xlcyI6WyJkZWZhdWx0LXJvbGVzLW1hc3RlciIsIm9mZmxpbmVfYWNjZXNzIiwidW1hX2F1dGhvcml6YXRpb24iXX0sInJlc291cmNlX2FjY2VzcyI6eyJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6Im9wZW5pZCBwcm9maWxlIGVtYWlsIiwic2lkIjoiNzFiYWM5MTAtNDdjNy00ZGQzLTg5Y2QtNDM5ZmMyNDc1NWNhIiwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJ1c2VyX2lkIjoiNDRhMGQ0ZjctNjc0NS00NjgxLWE1MTEtNmRjYmY1ODcxZDljIiwibmFtZSI6IkjGsMahbmcgR2lhbmciLCJwcmVmZXJyZWRfdXNlcm5hbWUiOiIwMzg4NjA4ODMzIiwiZ2l2ZW5fbmFtZSI6IkjGsMahbmcgR2lhbmcifQ.Ews3guwVgGIhQe2vLAHS0gDiqizPiedEW7x9HGiLmoPzE_AjWi_jgUhryexHaJDhLOJtXXJd82yKIUEybCWmZfMzWHg7SQM_MEszZfL4Snev4HUgeDitJMH5j9K0-OmiuX0VRAvzjb4LmI6PDswm5Nd-CcXTIYP3NkO8hA1M9DYAunzJgnfbqtTQuvPEbBrUyoDa5S-53xAF3DtQbwrjPAdukiFIX56TlDLriNXYEH2N7oa3yWRycWfK_oWDydRAnUDVHGKmosQuHfPBrC6jGqfuG_T0Z5o16TgHOgeEdxeInhqsM0zYM15rtmRhW0RIEAi1kJaQV2MT7GjShPqE9Q",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICI4ODk3MDE0YS01YWU4LTQ1MWItYmUxYi1lNzY3MjljNjI4NWIifQ.eyJleHAiOjE3NzM5MDg4MTcsImlhdCI6MTc0MjM3MjgxNywianRpIjoiNWFlODgyMzQtNGExNy00MmI0LTk1YzQtN2M3MmUyOTk4OThiIiwiaXNzIjoiaHR0cHM6Ly9kZXYtc3NvLmJhb2hpZW10YXNjby52bi9yZWFsbXMvbWFzdGVyIiwiYXVkIjoiaHR0cHM6Ly9kZXYtc3NvLmJhb2hpZW10YXNjby52bi9yZWFsbXMvbWFzdGVyIiwic3ViIjoiNDRhMGQ0ZjctNjc0NS00NjgxLWE1MTEtNmRjYmY1ODcxZDljIiwidHlwIjoiUmVmcmVzaCIsImF6cCI6InRhc2NvLWluc3VyYW5jZS1kZXYiLCJzZXNzaW9uX3N0YXRlIjoiNzFiYWM5MTAtNDdjNy00ZGQzLTg5Y2QtNDM5ZmMyNDc1NWNhIiwic2NvcGUiOiJvcGVuaWQgcHJvZmlsZSBlbWFpbCIsInNpZCI6IjcxYmFjOTEwLTQ3YzctNGRkMy04OWNkLTQzOWZjMjQ3NTVjYSJ9.fS9LIDY_QEgio7iSsit9gTmgbRhSS62oZlB-2sY6gus",
        "expires_in": 86400,
        "assessment_id": 5922
    }
    return ValidateInvitationResponse(data=vals)


@router.post("/done",
             response_model=ActionInvitationResponse)
async def done_remote_inspection(
        done_invitation_vals: ActionInvitationRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    vals = {
        "id": 5922
    }
    return ActionInvitationResponse(data=vals)


@router.post("/cancel",
             response_model=ActionInvitationResponse)
async def cancel_remote_inspection(
        done_invitation_vals: ActionInvitationRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    vals = {
        "id": 5922
    }
    return ActionInvitationResponse(data=vals)
