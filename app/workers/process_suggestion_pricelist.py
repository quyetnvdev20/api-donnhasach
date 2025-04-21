import asyncio
import aiohttp
import aio_pika
import json

from ..config import settings
import logging
from logging.handlers import RotatingFileHandler
from logging import Formatter
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from app.api.v1.endpoints.repair_suggesstion import get_and_update_repair_line

# Thiết lập logger
logger = logging.getLogger('worker')
file_handler = RotatingFileHandler('worker.log', backupCount=1)
handler = logging.StreamHandler()
file_handler.setFormatter(Formatter(
    '%(asctime)s %(levelname)s : %(message)s '
    '[in %(module)s: %(pathname)s:%(lineno)d]'
))
handler.setFormatter(Formatter(
    '%(asctime)s %(levelname)s: %(message)s '
    '[in %(module)s: %(pathname)s:%(lineno)d]'
))
logger.addHandler(file_handler)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Remove default logging config to avoid duplicate logs
logging.getLogger().handlers = []


# Create semaphore for limiting concurrent processing

class SuggestionPricelistProcessor:
    
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            try:
                body = json.loads(message.body.decode())
                logger.info(f"Processing message: {body}")

                body_data = body.get('kwargs')
                type = body_data.get('event_type', '')
                if type == 'GET_SUGGESTION_PRICELIST':
                    record_id = body_data.get('metadata', {}).get('record_id')
                    logger.info(f"Processing record ID: {record_id}")
                    
                    # Xử lý dữ liệu và cập nhật lên Odoo
                    result = await get_and_update_repair_line(record_id)
                    
                    if result:
                        logger.info(f"Successfully updated repair line for record_id {record_id}")
                    else:
                        logger.warning(f"Failed to update repair line for record_id {record_id}")
                else:
                    logger.warning(f"Unknown event type: {type}")
                
                # Message đã được xử lý trong context manager async with message.process()
                # nên không cần gọi message.ack() ở đây
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
                # Trong trường hợp lỗi, tin nhắn vẫn sẽ được nack tự động bởi context manager
                # và sẽ được đưa trở lại vào queue để xử lý sau
                raise

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def connect_to_rabbitmq(self):
        """Kết nối tới RabbitMQ với retry logic"""
        logger.info(f"Attempting to connect to RabbitMQ at {settings.RABBITMQ_URL}")
        return await aio_pika.connect_robust(
            settings.RABBITMQ_URL,
            loop=self.loop
        )

    async def start(self):
        logger.info("Starting suggestion pricelist processor worker")
        # Connect to RabbitMQ with retry
        connection = await self.connect_to_rabbitmq()
        channel = await connection.channel()
        
        # Giới hạn số lượng tin nhắn xử lý đồng thời
        await channel.set_qos(prefetch_count=1)

        # Declare exchange and queue
        exchange = await channel.declare_exchange(
            "suggestion.pricelist.direct",
            aio_pika.ExchangeType.DIRECT
        )
        queue = await channel.declare_queue(
            "suggestion.pricelist.processing",
            durable=True
        )

        # Bind queue to exchange
        await queue.bind(exchange, routing_key="suggestion.pricelist.processing")

        # Start consuming messages
        logger.info("Suggestion pricelist processor worker started")
        await queue.consume(self.process_message)

        try:
            # Keep the worker running
            await asyncio.Future(loop=self.loop)
        finally:
            await connection.close()

    def run(self):
        try:
            logger.info("Initializing suggestion pricelist processor worker")
            self.loop.run_until_complete(self.start())
        except KeyboardInterrupt:
            logger.info("Shutting down worker...")
        except Exception as e:
            logger.error(f"Fatal error in suggestion pricelist processor: {str(e)}", exc_info=True)
            raise
        finally:
            self.loop.close()

def main():
    processor = SuggestionPricelistProcessor()
    processor.run()

if __name__ == "__main__":
    main()