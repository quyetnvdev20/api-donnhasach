import redis.asyncio as redis
from redis.exceptions import ConnectionError
import json
import logging
from typing import Any, Dict, List, Optional, Union
from ..config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.redis_client = None
        self.default_expiry = settings.REDIS_DEFAULT_EXPIRY  # Thời gian hết hạn mặc định (giây)

    async def connect(self):
        """Kết nối đến Redis server"""
        try:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Connected to Redis successfully")
            return self.redis_client
        except ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def get_client(self):
        """Lấy Redis client, tạo kết nối mới nếu chưa có"""
        if self.redis_client is None:
            await self.connect()
        return self.redis_client

    async def set(self, key: str, value: Any, expiry: int = None) -> bool:
        """Lưu giá trị vào Redis với key"""
        client = await self.get_client()
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        expiry = expiry or self.default_expiry
        return await client.set(key, value, ex=expiry)

    async def get(self, key: str) -> Any:
        """Lấy giá trị từ Redis theo key"""
        client = await self.get_client()
        value = await client.get(key)
        
        if value is None:
            return None
            
        try:
            # Thử parse JSON
            return json.loads(value)
        except json.JSONDecodeError:
            # Nếu không phải JSON, trả về giá trị nguyên bản
            return value

    async def delete(self, key: str) -> int:
        """Xóa key khỏi Redis"""
        client = await self.get_client()
        return await client.delete(key)

    async def exists(self, key: str) -> bool:
        """Kiểm tra key có tồn tại trong Redis không"""
        client = await self.get_client()
        return await client.exists(key) > 0

    async def expire(self, key: str, seconds: int) -> bool:
        """Đặt thời gian hết hạn cho key"""
        client = await self.get_client()
        return await client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Lấy thời gian còn lại trước khi key hết hạn"""
        client = await self.get_client()
        return await client.ttl(key)

    async def incr(self, key: str, expiry: int = None) -> int:
        """Tăng giá trị của key lên 1, trả về giá trị sau khi tăng"""
        client = await self.get_client()
        value = await client.incr(key)
        
        # Nếu key mới được tạo (value = 1), set expiry
        if value == 1 and expiry:
            await client.expire(key, expiry)
        
        return value

    async def keys(self, pattern: str = "*") -> List[str]:
        """Lấy danh sách các key theo pattern"""
        client = await self.get_client()
        return await client.keys(pattern)

    async def hset(self, name: str, key: str, value: Any) -> int:
        """Lưu giá trị vào hash"""
        client = await self.get_client()
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return await client.hset(name, key, value)

    async def hget(self, name: str, key: str) -> Any:
        """Lấy giá trị từ hash"""
        client = await self.get_client()
        value = await client.hget(name, key)
        
        if value is None:
            return None
            
        try:
            # Thử parse JSON
            return json.loads(value)
        except json.JSONDecodeError:
            # Nếu không phải JSON, trả về giá trị nguyên bản
            return value

    async def hgetall(self, name: str) -> Dict[str, Any]:
        """Lấy tất cả giá trị từ hash"""
        client = await self.get_client()
        result = await client.hgetall(name)
        
        # Thử parse JSON cho mỗi giá trị
        for key, value in result.items():
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
                
        return result

    async def hdel(self, name: str, *keys) -> int:
        """Xóa các key khỏi hash"""
        client = await self.get_client()
        return await client.hdel(name, *keys)

    async def close(self):
        """Đóng kết nối Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Redis connection closed")

# Tạo instance Redis client để sử dụng trong ứng dụng
redis_client = RedisClient() 