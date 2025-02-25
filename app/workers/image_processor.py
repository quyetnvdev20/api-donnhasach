import asyncio
import aio_pika
import json
import cv2, numpy as np
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models.image import Image
from ..models.insurance_detail import InsuranceDetail
from ..config import settings, ClaimImageStatus
import logging
import requests
from openai import AsyncOpenAI
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
import google.generativeai as genai
from PIL import Image as PIL_Image
from io import BytesIO
from app.core.settings import ImageStatus, SessionStatus
from ..models.session import Session as SessionModel
from dateutil.relativedelta import relativedelta
from minio import Minio
import uuid
from ..services.firebase import FirebaseNotificationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


LIST_FIELD_REQUIRED = [
    'serial_number',
    'premium_amount'
]

async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        try:
            # Decode message
            body = json.loads(message.body.decode())
            logger.info(f"Processing message: {body}")

            # Get image from database
            db: Session = SessionLocal()
            image = db.query(Image).filter(Image.image_id == body.get("image_id")).first()

            if not image:
                logger.error(f"Image not found: {body.get('image_id')}")
                return

            # Update status to processing
            image.status = ClaimImageStatus.PROCESSING.value
            db.commit()

            # Process image here...
            # ... (your existing image processing code)

            # After processing is complete, update status and send notification
            image.status = ClaimImageStatus.SUCCESS.value
            db.commit()

            # Send notification if device token is available
            if image.device_token:
                notification_result = await FirebaseNotificationService.send_notification_to_device(
                    device_token=image.device_token,
                    title="Image Analysis Complete",
                    body="Your image has been successfully analyzed.",
                    data={
                        "image_id": image.image_id,
                        "session_id": image.session_id,
                        "status": image.status
                    }
                )
                logger.info(f"Notification result: {notification_result}")

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")

            # Update status to failed
            if 'image' in locals() and image:
                image.status = ClaimImageStatus.FAILED.value
                image.error_message = str(e)
                db.commit()

                # Send failure notification if device token is available
                if image.device_token:
                    await FirebaseNotificationService.send_notification_to_device(
                        device_token=image.device_token,
                        title="Image Analysis Failed",
                        body="There was an error analyzing your image.",
                        data={
                            "image_id": image.image_id,
                            "session_id": image.session_id,
                            "status": image.status
                        }
                    )
        finally:
            db.close()

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def connect_to_rabbitmq():
    """Kết nối tới RabbitMQ với retry logic"""
    logger.info(f"Attempting to connect to RabbitMQ at {settings.RABBITMQ_URL}")
    return await aio_pika.connect_robust(settings.RABBITMQ_URL)

async def main():
    # Connect to RabbitMQ with retry
    connection = await connect_to_rabbitmq()
    channel = await connection.channel()

    # Declare exchange and queue
    exchange = await channel.declare_exchange("image.analysis.direct", aio_pika.ExchangeType.DIRECT)
    queue = await channel.declare_queue("image.analysis.processing", durable=True)

    # Bind queue to exchange
    await queue.bind(exchange, routing_key="image.uploaded")

    # Start consuming messages
    logger.info("Image processor worker started")
    await queue.consume(process_message)

    try:
        await asyncio.Future()  # wait forever
    finally:
        await connection.close()

if __name__ == "__main__":
    asyncio.run(main())