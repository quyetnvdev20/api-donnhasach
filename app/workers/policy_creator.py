import asyncio
import aio_pika
import aiohttp
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
    url = f"{os.getenv('AUTH_BAOBAO_URL')}/user/access-token?user_id={user_id}"
    payload = {}
    headers = {
        'X-API-Key': os.getenv('AUTH_BAOBAO_API_KEY')
    }
    response = requests.request("GET", url, headers=headers, data=payload)
    return response.json().get("access_token")

def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization"""
    from decimal import Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    return obj

async def create_policy(session, insurance_details: dict, image_url: str) -> dict:
    " Gọi Core API để tạo đơn bảo hiểm"
    # TODO: Implement actual Core API call
    # Đây là mock data để test

    # Chuyển đổi thành đối tượng datetime
    date_start = datetime.strptime(insurance_details.get("insurance_start_date"), '%Y-%m-%dT%H:%M:%S')
    date_end = datetime.strptime(insurance_details.get("insurance_end_date"), '%Y-%m-%dT%H:%M:%S')
    policy_issued_datetime = datetime.strptime(insurance_details.get("policy_issued_datetime"), '%Y-%m-%dT%H:%M:%S')
    # Định dạng lại thành chuỗi mong muốn
    date_start = date_start.strftime('%Y-%m-%d %H:%M:%S')
    date_end = date_end.strftime('%Y-%m-%d %H:%M:%S')
    policy_date = policy_issued_datetime.strftime('%Y-%m-%d')

    premium_amount = float(insurance_details.get("premium_amount")) if insurance_details.get("premium_amount") else 0
    accident_premium = float(insurance_details.get("accident_premium")) if insurance_details.get("accident_premium") else 0
    number_seats = int(insurance_details.get("number_seats")) if insurance_details.get("number_seats") else 2

    data = {
        "license_plate": insurance_details.get("plate_number"),
        "vehicle_type_id": None,
        "channel_id": int(os.getenv("CHANNEL_ID")),
        "date_start": date_start,
        "date_end": date_end,
        "policy_date": policy_date,
        "vin_number": insurance_details.get("chassis_number", ''),
        "engine_number": insurance_details.get("engine_number", ''),
        "indicative": insurance_details.get("serial_number", ''),
        "tnds_insur_coverage": {
            "id": int(os.getenv("PRODUCT_CATEGORY_TNDS_BIKE_ID")),
            "name": "1. TNDS bắt buộc",
            "customer_amount": premium_amount - accident_premium,
            "premium_amount": premium_amount - accident_premium,
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
            "amount": accident_premium,
            "customer_amount": accident_premium,
            "premium_amount": accident_premium,
            "rate": 0.001,
            "number_seats": number_seats,
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
        "is_other_holders": False,
        "client_source": "acg_xm",
        "is_policy_indicative": True,
        "indicative_image_url": image_url,
        "responsible_id": int(session.responsible_id) if session.responsible_id else None
    }

    logger.info(f'create_policy.data: {str(data)}')

    headers = {
        'accept': 'application/json',
        'Authorization':  f'{await get_token_user(session.id_keycloak)}',
        'Content-Type': 'application/json'
    }

    url = f"{os.getenv('INSURANCE_API_URL')}/cobao-sync/cobao-insur-policy/insur-order"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            result = await response.json()
            result.update({
                'status_code': response.status
            })
            return result


async def create_policy_group_insured(session, images):
    if not images:
        raise ValueError("No images provided")

    insurance_details_first = None
    for img in images:
        if img.insurance_detail:
            insurance_details_first = img.insurance_detail
            break

    if not insurance_details_first:
        raise ValueError("First image has no insurance details")

    date_start_master = insurance_details_first.insurance_start_date
    date_end_master = insurance_details_first.insurance_end_date
    policy_date_master = insurance_details_first.policy_issued_datetime

    object_list = []

    for image in images:
        insurance_details = image.insurance_detail
        if not insurance_details:
            logger.warning(f"Skipping image {image.id} - no insurance details")
            continue

        try:
            date_start = insurance_details.insurance_start_date
            date_end = insurance_details.insurance_end_date
            policy_date = insurance_details.policy_issued_datetime

            date_start_master = min(date_start_master, date_start)
            date_end_master = max(date_end_master, date_end)
            policy_date_master = min(policy_date_master, policy_date)

            date_start_str = date_start.strftime('%Y-%m-%d %H:%M:%S')
            date_end_str = date_end.strftime('%Y-%m-%d %H:%M:%S')
            policy_date_str = policy_date.strftime('%Y-%m-%d')

            # Chuyển đổi các giá trị Decimal thành float
            premium_amount = decimal_to_float(getattr(insurance_details, "premium_amount", 0))
            accident_premium = decimal_to_float(getattr(insurance_details, "accident_premium", 0))

            number_seats = decimal_to_float(insurance_details.number_seats) if insurance_details.number_seats else 2
            data = {
                "car_owner": {
                    "customer_phone": insurance_details.phone_number,
                    "customer_type": "none",
                    "customer_vat": None,
                    "customer_name": insurance_details.owner_name,
                    "customer_cccd": None,
                    "customer_address": insurance_details.address
                },
                "license_plate": insurance_details.plate_number,
                "vin_number": getattr(insurance_details, "chassis_number", ''),
                "engine_number": getattr(insurance_details, "engine_number", ''),
                "date_start": date_start_str,
                "date_end": date_end_str,
                "policy_object_date": policy_date_str,
                "indicative_image_url": image.image_url,
                "indicative": getattr(insurance_details, "serial_number", ''),
                "tnds_insur_coverage": {
                    "id": int(os.getenv("PRODUCT_CATEGORY_TNDS_BIKE_ID")),
                    "name": "1. TNDS bắt buộc",
                    "customer_amount": decimal_to_float(premium_amount - accident_premium),
                    "premium_amount": decimal_to_float(premium_amount - accident_premium),
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
                    "amount": decimal_to_float(accident_premium),
                    "customer_amount": decimal_to_float(accident_premium),
                    "premium_amount": decimal_to_float(accident_premium),
                    "rate": 0.001,
                    "number_seats": number_seats,
                    "tariff_line_id": int(os.getenv("TARIFF_LINE_DRIVER_PASSENGER_ACCIDENT_ID")),
                    "name": "2. Tai nạn người ngồi trên xe"
                }
            }

            object_list.append(data)
        except Exception as e:
            logger.error(f"Error processing image {image.id}: {str(e)}")
            continue

    if not object_list:
        raise ValueError("No valid insurance details found in any image")

    # Định dạng datetime thành chuỗi cho policy_vals
    date_start_master_str = date_start_master.strftime('%Y-%m-%d %H:%M:%S')
    date_end_master_str = date_end_master.strftime('%Y-%m-%d %H:%M:%S')
    policy_date_master_str = policy_date_master.strftime('%Y-%m-%d')

    policy_vals = {
        "channel_id": int(os.getenv("CHANNEL_ID")),
        "date_start": date_start_master_str,
        "date_end": date_end_master_str,
        "policy_date": policy_date_master_str,
        "note": "",
        "car_owner": {
            "customer_phone": insurance_details_first.phone_number,
            "customer_type": "none",
            "customer_vat": None,
            "customer_name": insurance_details_first.owner_name,
            "customer_cccd": None,
            "customer_address": insurance_details_first.address
        },
        "client_source": "acg_xm",
        "is_policy_indicative": True,
        "object_list": object_list,
        "responsible_id": int(session.responsible_id) if session.responsible_id else None
    }

    logger.info(f'create_policy.data: {str(policy_vals)}')

    headers = {
        'accept': 'application/json',
        'Authorization':  f'{await get_token_user(session.id_keycloak)}',
        'Content-Type': 'application/json'
    }

    url = f"{os.getenv('INSURANCE_API_URL')}/cobao-sync/cobao-insur-policy/insur-order-multi-object"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=policy_vals) as response:
            result = await response.json()
            result.update({
                'status_code': response.status
            })
            return result


async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        db: Session = SessionLocal()
        try:
            # Decode message
            body = json.loads(message.body.decode())
            logger.info(f"Processing message: {body}")

            if body.get('session_type') == "individual_insured":
                image = db.query(Image).filter(Image.id == body["image_id"]).first()
                if not image:
                    raise ValueError(f"Image {body['image_id']} not found or not completed")

                session = db.query(SessionModel).filter(SessionModel.id == str(image.session_id)).first()
                if not session:
                    raise ValueError(f"Session {image.session_id} not found")

                try:
                    # Create policy
                    policy_result = await create_policy(session, body["insurance_details"], image.image_url)
                    if policy_result.get('status_code') != 200:
                        raise Exception(f"{policy_result.get('message')}")

                    image.status = ImageStatus.DONE
                    db.commit()
                except Exception as e:
                    logger.error(f"Error creating policy: {str(e)}")
                    image.status = ImageStatus.INVALID
                    image.error_message = f"Error creating policy: {str(e)}"
                    db.commit()

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            # Kiểm tra xem biến image đã được định nghĩa chưa
            if 'image' in locals():
                image.status = ImageStatus.INVALID
                image.error_message = f"Error processing message: {str(e)}"
                db.commit()
            # Nếu là group_insured, cập nhật trạng thái cho tất cả ảnh
            elif 'images' in locals():
                for img in images:
                    img.status = ImageStatus.INVALID
                    img.error_message = f"Error processing message: {str(e)}"
                db.commit()
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