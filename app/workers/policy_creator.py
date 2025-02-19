import asyncio
import aio_pika
import json
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models.image import Image
from ..models.session import Session as SessionModel
from ..config import settings
import logging
import requests
import os
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.settings import ImageStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def connect_to_rabbitmq():
    """
    Kết nối tới RabbitMQ với retry logic
    """
    logger.info(f"Attempting to connect to RabbitMQ at {settings.RABBITMQ_URL}")
    return await aio_pika.connect_robust(settings.RABBITMQ_URL)

async def get_token_user(user_id):
    # return 'eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICI3d1pHZmJDWlQxUGg1YVNzSXF1NkN4TWpIa3NmZE5Qa0FLb3doLUlnY0FNIn0.eyJleHAiOjE3NzE0OTIzOTcsImlhdCI6MTczOTk1NjM5NywianRpIjoiZmQwNWMxNWItYzcxYi00NGIxLWFlOTQtN2VjNWM1ODBkZmE5IiwiaXNzIjoiaHR0cHM6Ly9kZXYtc3NvLmJhb2hpZW10YXNjby52bi9yZWFsbXMvbWFzdGVyIiwiYXVkIjpbIm1hc3Rlci1yZWFsbSIsImFjY291bnQiXSwic3ViIjoiMDFhZWZmNDgtMTFjOS00ODg2LWJmNWMtNzU1MTA0OGVmM2RmIiwidHlwIjoiQmVhcmVyIiwiYXpwIjoidGFzY28taW5zdXJhbmNlLWRldiIsInNlc3Npb25fc3RhdGUiOiI4MGJkYmYyYy1mZGNmLTQ5ZTktODFhMy1jYjlmZWZlNzdmMDAiLCJhY3IiOiIxIiwiYWxsb3dlZC1vcmlnaW5zIjpbIiIsIioiXSwicmVhbG1fYWNjZXNzIjp7InJvbGVzIjpbImNyZWF0ZS1yZWFsbSIsImRlZmF1bHQtcm9sZXMtbWFzdGVyIiwib2ZmbGluZV9hY2Nlc3MiLCJhZG1pbiIsInVtYV9hdXRob3JpemF0aW9uIl19LCJyZXNvdXJjZV9hY2Nlc3MiOnsibWFzdGVyLXJlYWxtIjp7InJvbGVzIjpbInZpZXctaWRlbnRpdHktcHJvdmlkZXJzIiwidmlldy1yZWFsbSIsIm1hbmFnZS1pZGVudGl0eS1wcm92aWRlcnMiLCJpbXBlcnNvbmF0aW9uIiwiY3JlYXRlLWNsaWVudCIsIm1hbmFnZS11c2VycyIsInF1ZXJ5LXJlYWxtcyIsInZpZXctYXV0aG9yaXphdGlvbiIsInF1ZXJ5LWNsaWVudHMiLCJxdWVyeS11c2VycyIsIm1hbmFnZS1ldmVudHMiLCJtYW5hZ2UtcmVhbG0iLCJ2aWV3LWV2ZW50cyIsInZpZXctdXNlcnMiLCJ2aWV3LWNsaWVudHMiLCJtYW5hZ2UtYXV0aG9yaXphdGlvbiIsIm1hbmFnZS1jbGllbnRzIiwicXVlcnktZ3JvdXBzIl19LCJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6Im9wZW5pZCBwcm9maWxlIGVtYWlsIiwic2lkIjoiODBiZGJmMmMtZmRjZi00OWU5LTgxYTMtY2I5ZmVmZTc3ZjAwIiwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJ1c2VyX2lkIjoiMDFhZWZmNDgtMTFjOS00ODg2LWJmNWMtNzU1MTA0OGVmM2RmIiwibmFtZSI6Ikhp4bq_dSDEkOG7lyIsInByZWZlcnJlZF91c2VybmFtZSI6IjAzMzM0MDc0MjAiLCJnaXZlbl9uYW1lIjoiSGnhur91IMSQ4buXIiwiZW1haWwiOiJoaWV1ZHZAY2FycGxhLnZuIn0.eBlEkDc5uzR7qixwRwZkI1w68ulbMyt30BzwO7fp76eJwzwixU2jw6DW6ueR8JeX43Rf_kt35_oQ9ItbH3wUgIWS5epqbSIGY9SNHnQSYt9SVm_9lzyyAgZz0ZVya84apUUKH_YEobAtEjXZb8mQWIGlWn6UppB74XNR19eLE114GuE8GEaENbZA6lyVz3EvG4KAVr1wZazxlx707_8kV0jsoP7E2MvqG__zUTe6cgcvL-focw4W3a7CTHTbCFpDQDIifhTweoY8pFJsc6y9oPMIxDIinGzufqWk706j4yw19P4rQo2yixC84Std-c7DcznbUIjPYSM7Q5XUB-1OUQ'
    url = f"{os.getenv('AUTH_BAOBAO_URL')}/user/access-token?user_id={user_id}"
    payload = {}
    headers = {
        'X-API-Key': os.getenv('AUTH_BAOBAO_API_KEY')
    }
    response = requests.request("GET", url, headers=headers, data=payload)
    return response.json().get("access_token")

async def create_policy(insurance_details: dict, user_id: str) -> dict:
    " Gọi Core API để tạo đơn bảo hiểm"
    # TODO: Implement actual Core API call
    # Đây là mock data để test

    # Chuyển đổi thành đối tượng datetime
    date_start = datetime.strptime(insurance_details.get("insurance_start_date"), '%Y-%m-%dT%H:%M:%S')
    date_end = datetime.strptime(insurance_details.get("insurance_end_date"), '%Y-%m-%dT%H:%M:%S')
    # Định dạng lại thành chuỗi mong muốn
    date_start = date_start.strftime('%Y-%m-%d %H:%M:%S')
    date_end = date_end.strftime('%Y-%m-%d %H:%M:%S')

    data = {
        "license_plate": insurance_details.get("plate_number"),
        "vehicle_type_id": None,
        "channel_id": int(os.getenv("CHANNEL_ID")),
        "date_start": date_start,
        "date_end": date_end,
        "vin_number": insurance_details.get("chassis_number", ''),
        "engine_number": insurance_details.get("engine_number", ''),
        "tnds_insur_coverage": {
            "id": int(os.getenv("PRODUCT_CATEGORY_TNDS_BIKE_ID")),
            "name": "1. TNDS bắt buộc",
            "customer_amount": insurance_details.get("premium_amount") - insurance_details.get("accident_premium"),
            "premium_amount": insurance_details.get("premium_amount") - insurance_details.get("accident_premium"),
            "tariff_line_id": int(os.getenv("TARIFF_LINE_TNDS_BIKE_ID")),
            "detail_coverage": [
                {
                    "id": int(os.getenv("PRODUCT_CATEGORY_TNDS_BIKE_1_1_ID")),
                    "amount": 150_000_000,
                    "name": "1.1 Về sức khỏe, tính mạng"
                },
                {
                    "id": int(os.getenv("PRODUCT_CATEGORY_TNDS_BIKE_1_2_ID")),
                    "amount": 50_000_000,
                    "name": "1.2 Về tài sản"
                }
            ]
        },
        "driver_passenger_accident": {
            "id": int(os.getenv("PRODUCT_CATEGORY_DRIVER_PASSENGER_ACCIDENT_ID")),
            "amount": insurance_details.get("accident_premium"),
            "customer_amount": insurance_details.get("accident_premium"),
            "premium_amount": insurance_details.get("accident_premium"),
            "rate": 0.001,
            "number_seats": insurance_details.get("number_seats"),
            "tariff_line_id": int(os.getenv("TARIFF_LINE_DRIVER_PASSENGER_ACCIDENT_ID")),
            "name": "2. Tai nạn người ngồi trên xe"
        },
        "note": "",
        "car_owner": {
            "customer_phone": insurance_details.get("phone_number"),
            "customer_type": "none",
            "customer_vat": None,
            "customer_name": insurance_details.get("owner_name"),
            "customer_cccd": None,
            "customer_address": insurance_details.get("address")
        },
        "is_other_holders": False
    }

    logger.info(f'create_policy.data: {str(data)}')

    payload = json.dumps(data)
    headers = {
        'accept': 'application/json',
        'Authorization':  f'{await get_token_user(user_id)}',
        'Content-Type': 'application/json'
    }

    url = f"{os.getenv('INSURANCE_API_URL')}/cobao-sync/cobao-insur-policy/insur-order"

    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code != 200:
        logger.warning(f"Unexpected response status code: {response.status_code}")
        return {}

    return response.json()


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
            
            if image.status not in ("COMPLETED", 'completed'):
                logger.error(f"Image {body['image_id']} is not success")
                return
            
            session = db.query(SessionModel).filter(SessionModel.id == str(image.session_id)).first()
            user_id = session.id_keycloak

            try:
                # Create policy
                policy_result = await create_policy(body["insurance_details"], user_id)
                if not policy_result:
                    logger.error(f"Image {body['image_id']} create fail")
                    image.status = ImageStatus.INVALID
                    image.error_message = f"Image create policy fail"
                    db.commit()
                    return

                image.status = ImageStatus.DONE
                db.commit()

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