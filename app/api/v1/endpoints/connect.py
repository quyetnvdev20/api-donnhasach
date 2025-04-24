import base64
import os

from fastapi import APIRouter, Depends, HTTPException, status, Body, Header, UploadFile, File
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from typing import List, Optional
from ....database import get_db
from ...deps import get_current_user
from ....utils.erp_db import PostgresDB
from ....schemas.connect import ConnectRequest, ConnectResponse
import httpx
import json
import asyncio
import uuid
import logging
from datetime import datetime
from app.config import  settings, odoo
from app.utils.redis_client import redis_client
from typing import Annotated
import asyncio
import tempfile
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/",
             response_model=ConnectResponse,
             status_code=status.HTTP_200_OK)
async def connect_company_vendor(
        request: ConnectRequest,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
) -> ConnectResponse:
    """
    Approve a repair plan
    """
    response = await odoo.call_method_post(
        record_id=request.repair_id,
        model='insurance.claim.solution.repair',
        method='action_approve_pass_workflow',
        token=current_user.odoo_token,
        kwargs={'reason': request.approve_reason}
    )
    return ConnectResponse(id=response)