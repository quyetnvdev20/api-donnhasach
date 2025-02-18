import asyncio
import aio_pika
import json
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models.image import Image
from ..config import settings
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def connect_to_rabbitmq():
    """Kết nối tới RabbitMQ với retry logic"""
    logger.info(f"Attempting to connect to RabbitMQ at {settings.RABBITMQ_URL}")
    return await aio_pika.connect_robust(settings.RABBITMQ_URL)

async def create_policy(insurance_details: dict) -> dict:
    """
    Gọi Core API để tạo đơn bảo hiểm
    """
    # TODO: Implement actual Core API call
    # Đây là mock data để test
    return {
        "policy_number": "POL123456",
        "status": "ACTIVE"
    }

async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        try:
            # Decode message
            body = json.loads(message.body.decode())
            logger.info(f"Processing message: {body}")

            # Get image from database
            db: Session = SessionLocal()
            image = db.query(Image).filter(Image.id == body["image_id"]).first()
            if not image:
                logger.error(f"Image {body['image_id']} not found")
                return

            try:
                # Create policy
                policy_result = await create_policy(body["insurance_details"])

                # Publish event
                connection = await connect_to_rabbitmq()
                channel = await connection.channel()
                exchange = await channel.declare_exchange("acg.xm.direct", aio_pika.ExchangeType.DIRECT)

                await exchange.publish(
                    aio_pika.Message(
                        body=json.dumps({
                            "event_type": "POLICY_CREATED",
                            "image_id": str(image.id),
                            "session_id": str(image.session_id),
                            "policy_number": policy_result["policy_number"],
                            "status": policy_result["status"],
                            "timestamp": image.updated_at.isoformat()
                        }).encode(),
                        content_type="application/json"
                    ),
                    routing_key="policy.created"
                )

                await connection.close()

            except Exception as e:
                logger.error(f"Error creating policy: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
        finally:
            db.close()

async def main():
    # Connect to RabbitMQ with retry
    connection = await connect_to_rabbitmq()
    channel = await connection.channel()

    # Declare exchange and queue
    exchange = await channel.declare_exchange("acg.xm.direct", aio_pika.ExchangeType.DIRECT)
    queue = await channel.declare_queue("acg.xm.policy.creation", durable=True)
    
    # Bind queue to exchange
    await queue.bind(exchange, routing_key="image.processed")

    # Start consuming messages
    logger.info("Policy creator worker started")
    await queue.consume(process_message)

    try:
        await asyncio.Future()  # wait forever
    finally:
        await connection.close()

if __name__ == "__main__":
    asyncio.run(main()) 