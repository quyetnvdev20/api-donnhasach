import asyncio
import aio_pika
import json
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models.image import Image
from ..config import settings, ClaimImageStatus
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ..services.firebase import FirebaseNotificationService
from ..utils.erp_db import PostgresDB

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
            image = db.query(Image).filter(Image.analysis_id == body.get("analysis_id"),
                                           Image.assessment_id == body.get("assessment_id")).first()

            if not image:
                logger.error(f"Image analysis not found: {body.get('analysis_id')}")
                raise Exception(f"Image analysis not found: {body.get('analysis_id')}")

            # Update status to processing
            image.status = ClaimImageStatus.PROCESSING.value
            db.commit()
            db.refresh(image)

            # Process image here...
            logger.info(f"Start processing image analysis {image.analysis_id}")
            try:
                response = requests.post(
                    f"{settings.INSURANCE_PROCESSING_API_URL}/claim-image/claim-image-process",
                    json={"image_url": image.image_url},
                    headers={
                        "x-api-key": f"{settings.CLAIM_IMAGE_PROCESS_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    timeout=settings.CLAIM_IMAGE_PROCESS_TIMEOUT
                )
                if response.status_code != 200:
                    raise Exception(f"Failed to process image analysis {image.analysis_id}")

                image.status = ClaimImageStatus.SUCCESS.value
                image.list_json_data = response.json().get("data", [])
                db.commit()
                db.refresh(image)
            except Exception as e:
                logger.error(f"Error processing image analysis {image.analysis_id}: {str(e)}")
                image.status = ClaimImageStatus.FAILED.value
                image.error_message = str(e)
                db.commit()

            mapped_results = []
            if image.list_json_data:
                mapped_results = await mapping_assessment_item(image.list_json_data)
                image.results = json.dumps(mapped_results)
                db.commit()

            data_vals = {
                    "analysis_id": str(image.analysis_id),
                    "assessment_id": str(image.assessment_id),
                    "image_id": str(image.id),
                    "image_url": str(image.image_url),
                    # "status": image.status,
                    "results": json.dumps(mapped_results)
                }
            
            logger.info("Staring parsing data for notification")
            logger.info(f"Data vals: {data_vals}")

            notification_result = await FirebaseNotificationService.send_notification_to_topic(
                topic=f'tic_claim_{str(image.keycloak_user_id)}',
                title="Image Analysis Complete",
                body="Your image has been successfully analyzed.",
                data=data_vals
            )

            logger.info(f"Notification result: {notification_result}")

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            if image:
                image.status = ClaimImageStatus.FAILED.value
                image.error_message = str(e)
                db.commit()

                notification_result = await FirebaseNotificationService.send_notification_to_topic(
                    topic=f'tic_claim_{str(image.keycloak_user_id)}',
                    title="Image Analysis Failed",
                    body="There was an error analyzing your image.",
                    data={
                        "analysis_id": image.analysis_id,
                        "assessment_id": image.assessment_id,
                        "image_id": str(image.id),
                        "image_url": str(image.image_url),
                        # "status": image.status,
                        "results": json.dumps([])
                    }
                )
        finally:
            db.close()


async def mapping_assessment_item(json_data_list: list):
    """
    Map assessment items from json_data to database IDs

    Args:
        json_data_list (list): List of dictionaries containing category and state mappings
    """
    transformed_items = []

    # Transform the input data
    for data_dict in json_data_list:
        for category, state in data_dict.items():
            transformed_items.append({
                "damage_name": state,
                "item_name": category
            })

    if not transformed_items:
        return []

    # Build the WHERE clause with proper parameter placeholders
    placeholders = []
    values = []
    for i, item in enumerate(transformed_items):
        placeholders.append(f"(iclc.name = ${2 * i + 1} AND isc.name = ${2 * i + 2})")
        values.extend([item["item_name"], item["damage_name"]])

    query = f"""
        SELECT 
            iclc.id AS category_id,
            isc.id AS state_id,
            iclc.name AS category_name,
            isc.name AS state_name
        FROM insurance_claim_list_category iclc
        JOIN insurance_state_category isc ON 1=1
        WHERE {' OR '.join(placeholders)};
    """

    results = await PostgresDB.execute_query(query, values)
    print(results)

    if not results:
        return []

    # Map results using dict comprehension
    result_map = {
        (row["category_name"], row["state_name"]): {
            "damage_id": row["state_id"],
            "item_id": row["category_id"]
        } for row in results
    }

    # Update transformed items with IDs
    for item in transformed_items:
        key = (item["item_name"], item["damage_name"])
        if key in result_map:
            item.update(result_map[key])

    return transformed_items

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