import aio_pika
from ..config import settings
import json

async def get_rabbitmq_connection():
    return await aio_pika.connect_robust(settings.RABBITMQ_URL)

async def publish_event(event_type: str, payload: dict):
    connection = await get_rabbitmq_connection()
    channel = await connection.channel()
    
    exchange = await channel.declare_exchange(
        "acg.xm.direct",
        aio_pika.ExchangeType.DIRECT
    )
    
    message = aio_pika.Message(
        body=json.dumps(payload).encode(),
        content_type="application/json"
    )
    
    await exchange.publish(
        message,
        routing_key=event_type
    )
    
    await connection.close() 