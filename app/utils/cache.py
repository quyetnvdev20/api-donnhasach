import functools
import inspect
import logging
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional, Union, TypeVar, cast
from .redis_client import redis_client
from ..config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')

def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Tạo cache key từ prefix và các tham số
    """
    # Tạo chuỗi từ các tham số
    key_parts = [prefix]
    
    # Thêm các tham số vị trí
    if args:
        key_parts.append(str(args))
    
    # Thêm các tham số từ khóa, sắp xếp để đảm bảo tính nhất quán
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        key_parts.append(str(sorted_kwargs))
    
    # Nối các phần và tạo hash
    key_str = "_".join(key_parts)
    return f"{prefix}:{hashlib.md5(key_str.encode()).hexdigest()}"

def cache(ttl: Optional[int] = None, prefix: Optional[str] = None):
    """
    Decorator để cache kết quả của hàm bất đồng bộ
    
    Args:
        ttl: Thời gian sống của cache (giây), None để sử dụng giá trị mặc định
        prefix: Tiền tố cho cache key, mặc định là tên hàm
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Lấy tên hàm làm prefix nếu không được chỉ định
        cache_prefix = prefix or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Bỏ qua self hoặc cls nếu là phương thức của class
            if args and inspect.ismethod(func) and hasattr(args[0], func.__name__):
                cache_args = args[1:]
            else:
                cache_args = args
            
            # Tạo cache key
            cache_key = generate_cache_key(cache_prefix, *cache_args, **kwargs)
            
            # Thử lấy từ cache
            cached_result = await redis_client.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_result
            
            # Nếu không có trong cache, gọi hàm gốc
            logger.debug(f"Cache miss for {cache_key}")
            result = await func(*args, **kwargs)
            
            # Lưu kết quả vào cache
            if result is not None:
                await redis_client.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    
    return decorator

async def invalidate_cache(prefix: str, *args, **kwargs) -> bool:
    """
    Xóa cache với prefix và các tham số cụ thể
    """
    cache_key = generate_cache_key(prefix, *args, **kwargs)
    return await redis_client.delete(cache_key) > 0

async def invalidate_cache_pattern(pattern: str) -> int:
    """
    Xóa tất cả cache khớp với pattern
    """
    keys = await redis_client.keys(pattern)
    if not keys:
        return 0
    
    count = 0
    for key in keys:
        count += await redis_client.delete(key)
    
    return count 