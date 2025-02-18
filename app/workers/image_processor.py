import asyncio
import aio_pika
import json
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models.image import Image
from ..models.insurance_detail import InsuranceDetail
from ..config import settings
import logging
import requests
from openai import AsyncOpenAI
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def process_image(image_url: str) -> dict:
    """
    Sử dụng OpenAI Vision API để trích xuất thông tin từ ảnh giấy bảo hiểm
    """
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = """
    Hãy trích xuất chính xác các thông tin sau từ hình ảnh được cung cấp và trả về dưới dạng JSON:
    {
        "owner_name": "Chủ xe",
        "number_seats": "Số người được bảo hiểm",
        "liability_amount": "Mức trách nhiệm bảo hiểm",
        "accident_premium": "Phí bảo hiểm tai nạn",
        "address": "Địa chỉ",
        "plate_number": "Biển kiểm soát",
        "phone_number": "Điện thoại",
        "vin": "Số khung",
        "engine_number": "Số máy",
        "vehicle_type": "Loại xe",
        "insurance_period": {
        "start": "Thời gian bắt đầu (DD/MM/YYYY HH:mm)",
        "end": "Thời gian kết thúc (DD/MM/YYYY HH:mm)"
        },
        "premium_amount": "Tổng phí",
        "issue_date": "Cấp hồi (DD/MM/YYYY HH:mm)"
        }
        Lưu ý:
        - Chỉ trả về JSON, không thêm bất kỳ văn bản nào khác
        - Đảm bảo định dạng ngày tháng theo mẫu
    """

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    }
                ]
            }
        ],
        response_format={ "type": "json_object" }
    )

    # Parse JSON response
    try:
        result = json.loads(response.choices[0].message.content)

        # # Convert string dates to proper format
        # date_fields = [
        #     'insurance_start_date',
        #     'insurance_end_date',
        #     'premium_payment_due_date'
        # ]
        # for field in date_fields:
        #     if field in result and result.get(field):
        #         result[field] = datetime.strptime(
        #             result[field],
        #             '%Y-%m-%d'
        #         ).date().isoformat()
        #
        # # Convert policy issued datetime
        # if 'policy_issued_datetime' in result and result.get('policy_issued_datetime'):
        #     result['policy_issued_datetime'] = datetime.strptime(
        #         result['policy_issued_datetime'],
        #         '%d-%m-%Y'
        #     ).isoformat()

        # Convert premium amount to decimal
        if 'premium_amount' in result:
            result['premium_amount'] = float(str(result['premium_amount']).replace(',', '').replace('.', ''))

        return result

    except Exception as e:
        logger.error(f"Error parsing OpenAI response: {str(e)}")
        raise Exception("Failed to parse insurance information from image")

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

            # Update image status
            image.status = "PROCESSING"
            db.commit()

            try:
                # Process image
                insurance_info = await process_image(image.image_url)

                # Create insurance detail
                insurance_detail = InsuranceDetail(
                    image_id=image.id,
                    **insurance_info
                )
                db.add(insurance_detail)

                # Update image status
                image.status = "COMPLETED"
                image.json_data = insurance_info
                db.commit()

                # Publish event
                connection = await connect_to_rabbitmq()
                channel = await connection.channel()
                exchange = await channel.declare_exchange("acg.xm.direct", aio_pika.ExchangeType.DIRECT)

                await exchange.publish(
                    aio_pika.Message(
                        body=json.dumps({
                            "event_type": "IMAGE_PROCESSED",
                            "image_id": str(image.id),
                            "session_id": str(image.session_id),
                            "insurance_details": insurance_info,
                            "timestamp": image.updated_at.isoformat()
                        }).encode(),
                        content_type="application/json"
                    ),
                    routing_key="image.processed"
                )

                await connection.close()

            except Exception as e:
                logger.error(f"Error processing image: {str(e)}")
                image.status = "ERROR"
                db.commit()

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
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
    exchange = await channel.declare_exchange("acg.xm.direct", aio_pika.ExchangeType.DIRECT)
    queue = await channel.declare_queue("acg.xm.image.processing", durable=True)

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