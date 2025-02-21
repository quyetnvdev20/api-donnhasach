import asyncio
import json
from datetime import datetime
import logging
from sqlalchemy import and_
import aio_pika
from tenacity import retry, stop_after_attempt, wait_exponential

from ..database import SessionLocal
from ..models.image import Image
from ..models.session import Session
from ..config import settings
from app.core.settings import ImageStatus, SessionStatus

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

async def process_group_sessions():
    """
    Kiểm tra và xử lý các session group_insured
    """
    try:
        db = SessionLocal()
        logger.debug("Database session started.")
        
        # Lấy tất cả các session group_insured đang closed và chưa bị xóa
        active_sessions = db.query(Session).filter(
            and_(
                Session.policy_type == 'group_insured',
                Session.status == SessionStatus.CLOSED.value,
            )
        ).all()
        logger.info(f"Found {len(active_sessions)} active sessions to process.")

        for session in active_sessions:
            try:
                logger.debug(f"Processing session {session.id}.")
                # Lấy tất cả ảnh trong session (không bị xóa và không bị lỗi)
                all_images = db.query(Image).filter(
                    Image.session_id == session.id,
                    Image.status.notin_([
                        ImageStatus.FAILED.value
                    ])
                ).all()
                logger.info(f"Session {session.id}: Found {len(all_images)} valid images.")

                if not all_images:
                    logger.info(f"No valid images found in session {session.id}")
                    continue

                # Đếm số ảnh đã xử lý thành công
                processed_images = [
                    img for img in all_images 
                    if img.status == ImageStatus.COMPLETED.value and 
                    img.json_data != {} and 
                    img.json_data is not None
                ]
                logger.info(f"Session {session.id}: {len(processed_images)} images processed successfully.")

                # Kiểm tra xem số lượng ảnh đã xử lý có bằng tổng số ảnh không
                if len(processed_images) == len(all_images) and len(all_images) > 0:
                    logger.info(f"All {len(all_images)} images in session {session.id} processed successfully")

                    try:
                        # Gửi event
                        connection = await connect_to_rabbitmq()
                        logger.debug("Connected to RabbitMQ.")
                        channel = await connection.channel()
                        exchange = await channel.declare_exchange("acg.xm.direct", aio_pika.ExchangeType.DIRECT)
                        logger.debug("Exchange declared.")

                        # Tạo danh sách insurance_details từ các ảnh đã xử lý
                        all_insurance_details = [img.json_data for img in processed_images]

                        await exchange.publish(
                            aio_pika.Message(
                                body=json.dumps({
                                    "event_type": "IMAGE_PROCESSED",
                                    "session_id": str(session.id),
                                    "insurance_details": all_insurance_details,
                                    "session_type": 'group_insured',
                                    "timestamp": datetime.now().isoformat()
                                }).encode(),
                                content_type="application/json"
                            ),
                            routing_key="image.processed"
                        )
                        logger.info(f"Event published for session {session.id}.")

                        await connection.close()
                        logger.debug("RabbitMQ connection closed.")

                        # Cập nhật trạng thái session
                        session.status = SessionStatus.COMPLETED.value
                        db.commit()
                        logger.info(f"Session {session.id} status updated to COMPLETED.")
                        
                    except Exception as e:
                        logger.error(f"Error publishing event for session {session.id}: {str(e)}")
                        continue

                else:
                    logger.info(f"Session {session.id}: {len(processed_images)}/{len(all_images)} images processed")

            except Exception as e:
                logger.error(f"Error processing session {session.id}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Error in process_group_sessions: {str(e)}")
    finally:
        db.close()
        logger.debug("Database session closed.")

async def run_periodic_check():
    """
    Chạy kiểm tra định kỳ
    """
    while True:
        await process_group_sessions()
        # Đợi 30 giây trước khi kiểm tra lại
        await asyncio.sleep(30)

async def main():
    """
    Hàm main để khởi chạy worker
    """
    logger.info("Session processor worker started")
    await run_periodic_check()

if __name__ == "__main__":
    asyncio.run(main()) 