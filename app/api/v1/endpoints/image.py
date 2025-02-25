from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ....database import get_db
from ....models.image import Image
from ....schemas.image import ImageCreate, ImageResponse
from ....services.rabbitmq import publish_event
from ...deps import get_current_user
import uuid
from pydantic import BaseModel
from ....workers.image_processor import process_image, process_image_with_gemini, process_message
from app.core.settings import ImageStatus, SessionStatus
import aio_pika
import json
from datetime import datetime

router = APIRouter()

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@router.post("/images", response_model=ImageResponse)
async def create_image(image: ImageCreate, db: Session = Depends(get_db)):
    pass