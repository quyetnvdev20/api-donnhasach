import asyncio
import aio_pika
import json
import cv2, numpy as np
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
import google.generativeai as genai
from PIL import Image as PIL_Image
from io import BytesIO
from app.core.settings import ImageStatus, SessionStatus
from ..models.session import Session as SessionModel
from dateutil.relativedelta import relativedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


LIST_FIELD_REQUIRED = [
    'serial_number',
    'premium_amount'
]

async def process_image(image_url: str) -> dict:
    """
    Sử dụng OpenAI Vision API để trích xuất thông tin từ ảnh giấy bảo hiểm
    """
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = """
    Hãy trích xuất chính xác các thông tin sau từ hình ảnh được cung cấp và trả về dưới dạng JSON:
    {   "serial_number": "Số Serial (Ví dụ: AA00358056/25)",
        "owner_name": "Chủ xe",
        "number_seats": "Số người được bảo hiểm (Số)",
        "liability_amount": "Mức trách nhiệm bảo hiểm (Số)",
        "accident_premium": "Phí bảo hiểm tai nạn (Số)",
        "address": "Địa chỉ",
        "plate_number": "Biển kiểm soát",
        "phone_number": "Điện thoại",
        "chassis_number": "Số khung",
        "engine_number": "Số máy",
        "vehicle_type": "Loại xe",
        "insurance_start_date": "Thời gian bắt đầu (DD/MM/YYYY HH:mm:00)",
        "insurance_end_date": "Thời gian kết thúc (DD/MM/YYYY HH:mm:00)"
        "premium_amount": "TỔNG PHÍ (Số)",
        "policy_issued_datetime": "Cấp hồi (DD/MM/YYYY HH:mm:00)"
        }
        Lưu ý:
        - Chỉ trả về JSON, không thêm bất kỳ văn bản nào khác
        - Đảm bảo định dạng ngày tháng theo mẫu
        - Số tiền không có dấu phẩy hoặc dấu chấm phân cách và chỉ lấy số không lấy chữ
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
        logger.info(f'process_image.chat_gpt.gia tri tra ve tu chatgpt: {str(result)}')

        # Convert string dates to proper format
        date_fields = [
            'insurance_start_date',
            'insurance_end_date',
            'premium_payment_due_date',
            'policy_issued_datetime'
        ]
        for field in date_fields:
            if field in result and result.get(field):
                result[field] = datetime.strptime(
                    result[field],
                    '%d/%m/%Y %H:%M:%S'
                ).isoformat()

        # Convert policy issued datetime
        if 'premium_payment_due_date' in result and result.get('premium_payment_due_date'):
            result['premium_payment_due_date'] = datetime.strptime(
                result['premium_payment_due_date'],
                '%d/%m/%Y'
            ).isoformat()

        float_fields = [
            'premium_amount',
            'liability_amount',
            'accident_premium',
        ]

        for f in float_fields:
            if result.get(f):
                value = str(result[f])
                if '.' in value:
                    value = value.replace('.', '')
                result[f] = float(value)

        if 'number_seats' in result:
            result['number_seats'] = int(str(result['number_seats']))

        return result

    except Exception as e:
        logger.error(f"Error parsing OpenAI response: {str(e)}")
        raise Exception(f"Failed to parse insurance information from image: {str(e)}")

async def process_image_with_gemini(image_url: str) -> dict:
    """
    Sử dụng Google Gemini Vision API để trích xuất thông tin từ ảnh giấy bảo hiểm
    """
    # Cấu hình Gemini
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = """
    Hãy trích xuất chính xác các thông tin sau từ hình ảnh được cung cấp và trả về dưới dạng JSON:
    {
        "serial_number": "Số Serial (Ví dụ: AA00358056/25)",
        "owner_name": "Chủ xe",
        "number_seats": "Số người được bảo hiểm (Số)",
        "liability_amount": "Mức trách nhiệm bảo hiểm (Số)",
        "accident_premium": "Phí bảo hiểm tai nạn (Số)",
        "address": "Địa chỉ",
        "plate_number": "Biển kiểm soát",
        "phone_number": "Điện thoại",
        "chassis_number": "Số khung",
        "engine_number": "Số máy",
        "vehicle_type": "Loại xe",
        "insurance_start_date": "Thời gian bắt đầu (DD/MM/YYYY HH:mm:00)",
        "insurance_end_date": "Thời gian kết thúc (DD/MM/YYYY HH:mm:00)"
        "premium_amount": "TỔNG PHÍ (Số)",
        "policy_issued_datetime": "Cấp hồi (DD/MM/YYYY HH:mm:00)"
    }
    Lưu ý:
    - Chỉ trả về JSON, không thêm bất kỳ văn bản nào khác
    - Đảm bảo định dạng ngày tháng theo mẫu
    - Ngày giờ của thời gian kết thúc trùng với ngày giờ của thời gian bắt đầu, chỉ khác nhau mỗi năm, năm của thời gian kết thúc ở ngay dưới năm của thời gian bắt đầu
    - Số tiền không có dấu phẩy hoặc dấu chấm phân cách và chỉ lấy số không lấy chữ
    - - Các dấu tích v hoặc x là các điều kiện được chọn để lấy lên ví dụ: Loại xe, Số người được bảo hiểm, Mức trách nhiệm bảo hiểm
    """

    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
        cv2_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        # Convert images to grayscale
        input_gray = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2GRAY)
        ref_img = cv2.imread("/app/reference_full.jpg")
        ref_gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
        # Detect keypoints and compute descriptors using ORB
        orb = cv2.ORB_create(5000)  # Maximum 5000 keypoints
        kp1, des1 = orb.detectAndCompute(input_gray, None)
        kp2, des2 = orb.detectAndCompute(ref_gray, None)
        # Match descriptors using Brute-Force Matcher with Hamming distance
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)  # Sort matches by distance
        good_matches = matches[:50]
        # Extract coordinates of matched keypoints
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        # Compute homography matrix using RANSAC
        matrix, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        # Get dimensions of the reference image
        h, w = ref_img.shape[:2]
        # Apply perspective transformation to align the input image
        aligned_img = cv2.warpPerspective(cv2_image, matrix, (w, h))
        aligned_rgb = cv2.cvtColor(aligned_img, cv2.COLOR_BGR2RGB)
        image = PIL_Image.fromarray(aligned_rgb)

        # Tải ảnh từ URL
        # response = requests.get(image_url)
        # response.raise_for_status()
        # image = PIL_Image.open(BytesIO(response.content))

        # Gọi Gemini API
        response = model.generate_content([prompt, image])
        
        # Log raw response để debug
        logger.info(f'Raw Gemini response: {response.text}')
        
        try:
            # Lấy kết quả JSON từ response
            # Thử tìm và parse phần JSON trong response
            import re
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
            else:
                raise ValueError("No JSON object found in response")
                
            logger.info(f'process_image.gemini.gia tri tra ve tu gemini: {str(result)}')

            # Xử lý các trường datetime
            date_fields = [
                'insurance_start_date',
                'insurance_end_date',
                'premium_payment_due_date',
                'policy_issued_datetime'
            ]
            for field in date_fields:
                if field in result and result.get(field):
                    try:
                        result[field] = datetime.strptime(
                            result[field],
                            '%d/%m/%Y %H:%M:%S'
                        ).isoformat()
                    except:
                        result[field] = datetime.strptime(
                            result[field],
                            '%d/%m/%Y 00:00:00'
                        ).isoformat()

            """set default ngày cấp đơn, thời hạn hiệu lực nếu không đọc được từ ảnh
                ngày cấp: now
                ngày hiệu lực: now - 1 ngày
                ngày hết hiệu lực: now + 1 năm
            """
            if not result.get('insurance_start_date'):
                result['insurance_start_date'] = datetime.now().isoformat()
                result['insurance_end_date'] = (datetime.now()  + relativedelta(years=1)).isoformat()
                result['policy_issued_datetime'] = (datetime.now()  - relativedelta(days=1)).isoformat()
                result['is_suspecting_wrongly'] = True

            # Xử lý các trường số
            float_fields = [
                'premium_amount',
                'liability_amount',
                'accident_premium',
            ]
            for f in float_fields:
                if result.get(f):
                    value = str(result[f])
                    if '.' in value:
                        value = value.replace('.', '')
                    result[f] = float(value)

            if result.get('number_seats'):
                result['number_seats'] = int(str(result['number_seats']))

            if result.get('serial_number'):
                result['serial_number'] = result.get('serial_number').replace(' ', '')

            return result

        except Exception as e:
            logger.error(f"Error parsing Gemini response: {str(e)}")
            logger.error(f"Response content: {response.text}")
            raise

    except Exception as e:
        logger.error(f"Error processing image with Gemini: {str(e)}")
        raise Exception(f"Failed to process insurance information from image: {str(e)}")

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
            image.status = ImageStatus.PROCESSING
            db.commit()

            try:
                # Process image
                insurance_info = await process_image_with_gemini(image.image_url)

                is_suspecting_wrongly = insurance_info.get('is_suspecting_wrongly')
                del insurance_info['is_suspecting_wrongly']

                # Create insurance detail
                insurance_detail = InsuranceDetail(
                    image_id=image.id,
                    **insurance_info
                )
                db.add(insurance_detail)
                db.commit()

                # Kiểm tra các trường bắt buộc
                missing_fields = []
                for field in LIST_FIELD_REQUIRED:
                    if not insurance_info.get(field):
                        missing_fields.append(field)

                if missing_fields:
                    error_message = f"Missing required fields: {', '.join(missing_fields)}"
                    logger.error(error_message)
                    raise ValueError(error_message)

                # Update image status
                image.status = ImageStatus.COMPLETED
                image.json_data = insurance_info
                image.is_suspecting_wrongly = is_suspecting_wrongly
                db.commit()

                session = db.query(SessionModel).filter(SessionModel.id == str(image.session_id)).first()
                if not session:
                    raise ValueError(f"Session {image.session_id} not found")

                if session.policy_type == 'group_insured':
                    return

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
                            "session_type": 'individual_insured',
                            "timestamp": image.updated_at.isoformat()
                        }).encode(),
                        content_type="application/json"
                    ),
                    routing_key="image.processed"
                )

                await connection.close()

            except ValueError as e:
                logger.error(f"Error processing image: {str(e)}")
                image.status = ImageStatus.FAILED
                image.json_data = insurance_info
                image.error_message = str(e)
                db.commit()
            except Exception as e:
                logger.error(f"Error processing image: {str(e)}")
                image.status = ImageStatus.FAILED
                image.json_data = insurance_info
                image.error_message = str(e)
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