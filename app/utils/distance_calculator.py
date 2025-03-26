import httpx
import logging
import math
import json
from typing import Tuple, Optional, Dict
from ..config import settings, odoo
from functools import lru_cache
import asyncio
import time
from datetime import datetime, timedelta
from ..utils.redis_client import redis_client
from ..utils.erp_db import PostgresDB
logger = logging.getLogger(__name__)

# Redis key prefix for geocoded coordinates
REDIS_GEOCODE_PREFIX = "geocode:"
# Redis expiration time for geocoded coordinates (30 days in seconds)
REDIS_GEOCODE_EXPIRY = 30 * 24 * 60 * 60

HERE_MAPS_URL = "https://geocode.search.hereapi.com/v1/geocode"

# Cache cho các tọa độ đã được geocode
_geocode_cache = {}

# Cache cho các tọa độ đã được geocode với thời gian hết hạn (1 tháng)
# Format: {address_normalized: {"coords": (lat, lng), "expires_at": timestamp}}
_geocode_cache_with_expiry = {}

# Cache cho các khoảng cách đã được tính
_distance_cache = {}

async def geocode_address_with_cache(address: str) -> Optional[Tuple[float, float]]:
    """
    Chuyển đổi địa chỉ thành tọa độ (latitude, longitude) sử dụng Google Maps Geocoding API
    
    Args:
        address: Địa chỉ cần chuyển đổi
        
    Returns:
        Tuple (latitude, longitude) hoặc None nếu không thể chuyển đổi
    """
    if not address or not address.strip():
        return None
    
    # Chuẩn hóa địa chỉ để sử dụng làm key trong cache
    normalized_address = address.strip().lower()
    
    # Kiểm tra cache có thời hạn trước
    current_time = time.time()
    if normalized_address in _geocode_cache_with_expiry:
        cache_entry = _geocode_cache_with_expiry[normalized_address]
        # Kiểm tra xem cache có còn hiệu lực không
        if cache_entry["expires_at"] > current_time:
            return cache_entry["coords"]
        else:
            # Xóa cache đã hết hạn
            del _geocode_cache_with_expiry[normalized_address]
    
    # Kiểm tra cache thông thường
    if normalized_address in _geocode_cache:
        return _geocode_cache[normalized_address]
        
    try:
        # Sử dụng Here Maps Geocoding API
        api_key = settings.HERE_MAPS_API_KEY
        url = f"{HERE_MAPS_URL}?q={address}&apiKey={api_key}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            
            if data["status"] == "OK" and data["results"]:
                location = data["results"][0]["geometry"]["location"]
                coords = (location["lat"], location["lng"])
                
                # Lưu vào cache thông thường
                _geocode_cache[normalized_address] = coords
                
                # Lưu vào cache có thời hạn (1 tháng)
                expires_at = current_time + (30 * 24 * 60 * 60)  # 30 days in seconds
                _geocode_cache_with_expiry[normalized_address] = {
                    "coords": coords,
                    "expires_at": expires_at
                }
                
                return coords
            else:
                logger.warning(f"Không thể geocode địa chỉ: {address}. Status: {data['status']}")
                # Lưu None vào cache để tránh gọi lại API cho địa chỉ không hợp lệ
                _geocode_cache[normalized_address] = None
                return None
                
    except Exception as e:
        logger.error(f"Lỗi khi geocode địa chỉ {address}: {str(e)}")
        return None


async def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """
    Chuyển đổi địa chỉ thành tọa độ (latitude, longitude) sử dụng Google Maps Geocoding API
    
    Args:
        address: Địa chỉ cần chuyển đổi
        
    Returns:
        Tuple (latitude, longitude) hoặc None nếu không thể chuyển đổi
    """
    if not address or not address.strip():
        return None
    
    # Chuẩn hóa địa chỉ để sử dụng làm key trong cache
    normalized_address = address.strip().lower()
    
    # STEP 1: Kiểm tra Redis cache
    redis_key = f"{REDIS_GEOCODE_PREFIX}{normalized_address}"
    try:
        redis_coords = await redis_client.get(redis_key)
        if redis_coords:
            logger.debug(f"[1] Found coordinates for '{normalized_address}' in Redis cache")
            # Convert list back to tuple
            return tuple(redis_coords) if isinstance(redis_coords, list) else redis_coords
    except Exception as e:
        logger.warning(f"Error accessing Redis for geocode: {str(e)}")
    
    # STEP 2: Kiểm tra cache có thời hạn
    current_time = time.time()
    if normalized_address in _geocode_cache_with_expiry:
        cache_entry = _geocode_cache_with_expiry[normalized_address]
        # Kiểm tra xem cache có còn hiệu lực không
        if cache_entry["expires_at"] > current_time:
            coords = cache_entry["coords"]
            logger.debug(f"[2] Found coordinates for '{normalized_address}' in expiry cache")
            
            # Cập nhật vào Redis để lần sau lấy từ Redis
            try:
                # Convert tuple to list for Redis storage
                coords_list = list(coords) if isinstance(coords, tuple) else coords
                await redis_client.set(redis_key, coords_list, expiry=REDIS_GEOCODE_EXPIRY)
            except Exception as e:
                logger.warning(f"Error saving coordinates to Redis: {str(e)}")
                
            return coords
        else:
            # Xóa cache đã hết hạn
            del _geocode_cache_with_expiry[normalized_address]
    
    # STEP 3: Kiểm tra cache thông thường
    if normalized_address in _geocode_cache:
        coords = _geocode_cache[normalized_address]
        logger.debug(f"[3] Found coordinates for '{normalized_address}' in regular cache")
        
        # Cập nhật vào Redis để lần sau lấy từ Redis
        if coords is not None:
            try:
                # Convert tuple to list for Redis storage
                coords_list = list(coords) if isinstance(coords, tuple) else coords
                await redis_client.set(redis_key, coords_list, expiry=REDIS_GEOCODE_EXPIRY)
                
                # Cập nhật vào cache có thời hạn
                expires_at = current_time + (30 * 24 * 60 * 60)  # 30 days in seconds
                _geocode_cache_with_expiry[normalized_address] = {
                    "coords": coords,
                    "expires_at": expires_at
                }
            except Exception as e:
                logger.warning(f"Error saving coordinates to Redis: {str(e)}")
                
        return coords
        
    # STEP 4: Nếu không có trong cache, gọi Google Maps API
    try:
        # Sử dụng Google Maps Geocoding API
        api_key = settings.HERE_MAPS_API_KEY
        url = f"{HERE_MAPS_URL}?q={address}&apiKey={api_key}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            
            if data["status"] == "OK" and data["results"]:
                location = data["results"][0]["geometry"]["location"]
                coords = (location["lat"], location["lng"])
                
                # Lưu vào cache thông thường
                _geocode_cache[normalized_address] = coords
                
                # Lưu vào cache có thời hạn (1 tháng)
                expires_at = current_time + (30 * 24 * 60 * 60)  # 30 days in seconds
                _geocode_cache_with_expiry[normalized_address] = {
                    "coords": coords,
                    "expires_at": expires_at
                }
                
                # Lưu vào Redis
                try:
                    # Convert tuple to list for Redis storage
                    coords_list = list(coords)
                    await redis_client.set(redis_key, coords_list, expiry=REDIS_GEOCODE_EXPIRY)
                    logger.debug(f"[4] Saved coordinates for '{normalized_address}' to Redis")
                except Exception as e:
                    logger.warning(f"Error saving coordinates to Redis: {str(e)}")
                
                return coords
            else:
                logger.warning(f"Không thể geocode địa chỉ: {address}.")
                # Lưu None vào cache để tránh gọi lại API cho địa chỉ không hợp lệ
                _geocode_cache[normalized_address] = None
                return None
                
    except Exception as e:
        logger.error(f"Lỗi khi geocode địa chỉ {address}: {str(e)}")
        return None

def calculate_distance_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Tính khoảng cách giữa hai điểm trên trái đất sử dụng công thức Haversine
    
    Args:
        lat1, lon1: Tọa độ điểm thứ nhất
        lat2, lon2: Tọa độ điểm thứ hai
        
    Returns:
        Khoảng cách tính bằng km
    """
    # Bán kính trái đất tính bằng km
    R = 6371.0
    
    # Chuyển đổi độ sang radian
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Hiệu số
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    # Công thức Haversine
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return distance

async def calculate_distance_between_addresses(location_address: str, garage_address: str) -> float:
    """
    Tính khoảng cách giữa hai địa chỉ
    
    Args:
        location_address: Địa chỉ nơi xảy ra tổn thất
        garage_address: Địa chỉ gara sửa chữa
        
    Returns:
        Khoảng cách tính bằng km, hoặc 0 nếu không thể tính toán
    """
    try:
        # Nếu một trong hai địa chỉ trống, trả về 0
        if not location_address or not garage_address:
            return 0.0
            
        # Chuyển đổi địa chỉ thành tọa độ
        location_coords = await geocode_address(location_address)
        garage_coords = await geocode_address(garage_address)
        
        # Nếu không thể chuyển đổi một trong hai địa chỉ, trả về 0
        if not location_coords or not garage_coords:
            return 0.0
            
        # Tính khoảng cách
        distance = calculate_distance_haversine(
            location_coords[0], location_coords[1],
            garage_coords[0], garage_coords[1]
        )
        
        return round(distance, 2)  # Làm tròn đến 2 chữ số thập phân
        
    except Exception as e:
        logger.error(f"Lỗi khi tính khoảng cách: {str(e)}")
        return 0.0

async def calculate_distance_with_cache(location_address: str, garage_address: str) -> float:
    """
    Tính khoảng cách giữa hai địa chỉ với cache để tránh gọi API nhiều lần
    
    Args:
        location_address: Địa chỉ nơi xảy ra tổn thất
        garage_address: Địa chỉ gara sửa chữa
        
    Returns:
        Khoảng cách tính bằng km, hoặc 0 nếu không thể tính toán
    """
    # Chuẩn hóa địa chỉ
    if not location_address or not garage_address:
        return 0.0
        
    location_normalized = location_address.strip().lower()
    garage_normalized = garage_address.strip().lower()
    
    # Tạo key cho cache (sắp xếp địa chỉ để đảm bảo A->B và B->A có cùng key)
    cache_key = tuple(sorted([location_normalized, garage_normalized]))
    
    # Kiểm tra cache
    if cache_key in _distance_cache:
        return _distance_cache[cache_key]
    
    # Tính khoảng cách nếu không có trong cache
    distance = await calculate_distance_between_addresses(location_address, garage_address)
    
    # Lưu vào cache
    _distance_cache[cache_key] = distance
    
    return distance

async def calculate_distance_from_coords_to_address(lat: float, lng: float, address: str) -> float:
    """
    Tính khoảng cách từ tọa độ đến một địa chỉ
    
    Args:
        lat: Vĩ độ
        lng: Kinh độ
        address: Địa chỉ đích
        
    Returns:
        Khoảng cách tính bằng km, hoặc 0 nếu không thể tính toán
    """
    try:
        # Nếu địa chỉ trống, trả về 0
        if not address:
            return 0.0
            
        # Chuyển đổi địa chỉ thành tọa độ
        address_coords = await geocode_address(address)
        # logger.info(f"address_coords: {address_coords}")
        
        # Nếu không thể chuyển đổi địa chỉ, trả về 0
        if not address_coords:
            return 0.0
            
        # Tính khoảng cách
        distance = calculate_distance_haversine(
            lat, lng,
            address_coords[0], address_coords[1]
        )
        
        return round(distance, 2)  # Làm tròn đến 2 chữ số thập phân
        
    except Exception as e:
        logger.error(f"Lỗi khi tính khoảng cách từ tọa độ đến địa chỉ: {str(e)}")
        return 0.0

async def  calculate_distance_from_coords_to_address_with_cache(lat: float, lng: float, address: str) -> float:
    """
    Tính khoảng cách từ tọa độ đến một địa chỉ với cache
    
    Args:
        lat: Vĩ độ
        lng: Kinh độ
        address: Địa chỉ đích
        
    Returns:
        Khoảng cách tính bằng km, hoặc 0 nếu không thể tính toán
    """
    # Nếu địa chỉ trống, trả về 0
    if not address:
        return 0.0
        
    # Chuẩn hóa địa chỉ
    address_normalized = address.strip().lower()
    
    # Tạo key cho cache
    coords_key = f"{lat:.6f},{lng:.6f}"
    cache_key = (coords_key, address_normalized)
    
    # Kiểm tra cache
    if cache_key in _distance_cache:
        return _distance_cache[cache_key]
    
    # Tính khoảng cách nếu không có trong cache
    distance = await calculate_distance_from_coords_to_address(lat, lng, address)
    
    # Lưu vào cache
    _distance_cache[cache_key] = distance
    
    return distance

def format_distance(distance: float) -> str:
    """
    Định dạng khoảng cách thành chuỗi với đơn vị
    
    Args:
        distance: Khoảng cách tính bằng km
        
    Returns:
        Chuỗi khoảng cách với đơn vị, ví dụ: "20.4 km"
    """
    if distance < 1:
        # Chuyển đổi sang mét nếu nhỏ hơn 1km
        meters = int(distance * 1000)
        return f"{meters} m"
    else:
        # Giữ nguyên km nếu lớn hơn hoặc bằng 1km
        return f"{distance:.1f} km"

def save_cache_to_file(file_path: str = "distance_cache.json"):
    """Lưu cache vào file để sử dụng lại sau khi khởi động lại ứng dụng"""
    try:
        # Chuyển đổi cache thành định dạng có thể serialize
        geocode_cache_serializable = {}
        for key, value in _geocode_cache.items():
            if value is not None:
                geocode_cache_serializable[key] = value
        
        # Chuyển đổi cache có thời hạn
        geocode_cache_with_expiry_serializable = {}
        for key, value in _geocode_cache_with_expiry.items():
            if value["coords"] is not None:
                geocode_cache_with_expiry_serializable[key] = value
        
        # Chuyển đổi tuple key thành string để có thể serialize
        distance_cache_serializable = {}
        for key, value in _distance_cache.items():
            distance_cache_serializable[str(key)] = value
        
        cache_data = {
            "geocode_cache": geocode_cache_serializable,
            "geocode_cache_with_expiry": geocode_cache_with_expiry_serializable,
            "distance_cache": distance_cache_serializable
        }
        
        with open(file_path, 'w') as f:
            json.dump(cache_data, f)
            
        logger.info(f"Đã lưu cache vào file {file_path}")
    except Exception as e:
        logger.error(f"Lỗi khi lưu cache vào file: {str(e)}")

def load_cache_from_file(file_path: str = "distance_cache.json"):
    """Đọc cache từ file"""
    try:
        with open(file_path, 'r') as f:
            cache_data = json.load(f)
            
        # Khôi phục geocode cache
        if "geocode_cache" in cache_data:
            _geocode_cache.update(cache_data["geocode_cache"])
        
        # Khôi phục geocode cache có thời hạn
        if "geocode_cache_with_expiry" in cache_data:
            _geocode_cache_with_expiry.update(cache_data["geocode_cache_with_expiry"])
        
        # Khôi phục distance cache, chuyển đổi string key thành tuple
        if "distance_cache" in cache_data:
            for key_str, value in cache_data["distance_cache"].items():
                # Chuyển đổi string key thành tuple
                key_tuple = tuple(eval(key_str))
                _distance_cache[key_tuple] = value
                
        logger.info(f"Đã đọc cache từ file {file_path}")
    except FileNotFoundError:
        logger.info(f"Không tìm thấy file cache {file_path}")
    except Exception as e:
        logger.error(f"Lỗi khi đọc cache từ file: {str(e)}")

# Hàm khởi tạo cache khi ứng dụng khởi động
def initialize_cache():
    """Khởi tạo cache khi ứng dụng khởi động"""
    load_cache_from_file()

# Hàm lưu cache khi ứng dụng tắt
def shutdown_cache():
    """Lưu cache khi ứng dụng tắt"""
    save_cache_to_file()

async def calculate_distances_batch_from_coords(lat: float, lng: float, addresses: list) -> dict:
    """
    Tính khoảng cách từ một tọa độ đến nhiều địa chỉ trong một lần gọi
    
    Args:
        lat: Vĩ độ
        lng: Kinh độ
        addresses: Danh sách các địa chỉ cần tính khoảng cách
        
    Returns:
        Dictionary với key là địa chỉ và value là một dict chứa khoảng cách (km) và thời gian di chuyển bằng xe máy (phút)
    """
    result = {}
    
    # Tạo key cho tọa độ
    coords_key = f"{lat:.6f},{lng:.6f}"
    
    # Danh sách các địa chỉ cần tính khoảng cách (không có trong cache)
    addresses_to_geocode = []
    
    # Kiểm tra cache trước
    for address in addresses:
        if not address:
            result[address] = {"distance": 0.0, "travel_time_minutes": 0}
            continue
            
        # Chuẩn hóa địa chỉ
        address_normalized = address.strip().lower()
        cache_key = (coords_key, address_normalized)
        
        # Nếu đã có trong cache, lấy từ cache
        if cache_key in _distance_cache:
            distance = _distance_cache[cache_key]
            # Tính thời gian di chuyển bằng xe máy (phút) với tốc độ trung bình 30 km/h
            travel_time_minutes = round((distance / 30) * 60)
            result[address] = {"distance": distance, "travel_time_minutes": travel_time_minutes}
        else:
            # Nếu chưa có trong cache, thêm vào danh sách cần tính
            addresses_to_geocode.append((address, address_normalized))
    
    # Nếu có địa chỉ cần tính khoảng cách
    if addresses_to_geocode:
        # Geocode tất cả các địa chỉ cùng một lúc
        geocode_tasks = [geocode_address_with_cache(addr) for addr, _ in addresses_to_geocode]
        geocode_results = await asyncio.gather(*geocode_tasks)
        
        # Tính khoảng cách cho từng địa chỉ
        for i, (address, address_normalized) in enumerate(addresses_to_geocode):
            coords = geocode_results[i]
            
            if coords:
                # Tính khoảng cách
                distance = calculate_distance_haversine(
                    lat, lng,
                    coords[0], coords[1]
                )
                distance = round(distance, 2)
                # Tính thời gian di chuyển bằng xe máy (phút) với tốc độ trung bình 30 km/h
                travel_time_minutes = round((distance / 30) * 60)
            else:
                distance = 0.0
                travel_time_minutes = 0
                
            # Lưu vào kết quả và cache
            result[address] = {"distance": distance, "travel_time_minutes": travel_time_minutes}
            cache_key = (coords_key, address_normalized)
            _distance_cache[cache_key] = distance
    
    return result 

async def find_nearby_garages(lat: float, lng: float, garage_list: list) -> dict:
    """
    Tìm các gara sửa chữa trong phạm vi bán kính cho trước từ vị trí người dùng
    
    Args:
        lat: Vĩ độ của người dùng
        lng: Kinh độ của người dùng
        garage_list: Danh sách các gara cần kiểm tra, mỗi phần tử là một dict chứa thông tin gara
                    với ít nhất trường 'id' và 'address'
        
    Returns:
        Dictionary với key là id của gara và value là thông tin gara bao gồm:
        - id: ID của gara
        - address: Địa chỉ gara
        - name: Tên gara
        - distance: Khoảng cách từ vị trí người dùng đến gara (km)
        - travel_time_minutes: Thời gian di chuyển bằng xe máy (phút)
        - coordinates: Tọa độ của gara (lat, lng)
    """
    start_time = time.time()
    result = {}
    memory_cache_hits = 0
    redis_hits = 0
    api_calls = 0
    
    try:
        # Validate input parameters
        if not isinstance(garage_list, list) or len(garage_list) == 0:
            logger.error("garage_list must be a non-empty list")
            return {}
            
        if not (isinstance(lat, (int, float)) and isinstance(lng, (int, float))):
            logger.error("lat and lng must be numeric values")
            return {}
        
        # Lọc ra các gara có địa chỉ hợp lệ
        valid_garages = []
        for garage in garage_list:
            if isinstance(garage, dict):
                garage_id = garage.get('id')
                address = garage.get('address', '').strip() if garage.get('address') else ''
                name = garage.get('name', '').strip() if garage.get('name') else ''
                
                if garage_id and address and name:
                    valid_garages.append((garage_id, address, name))
        
        if not valid_garages:
            logger.warning("No valid garages found in the provided list")
            return {}
            
        # Tạo key cho tọa độ người dùng
        coords_key = f"{lat:.6f},{lng:.6f}"
        
        # Phase 1: Process all garages using in-memory cache first
        processed_garages = {}  # Dictionary to track processed garages
        need_redis_check = []   # Garages that need Redis lookup
        need_geocoding = []     # Garages that need geocoding API calls
        
        current_time = time.time()
        
        # First pass: Check in-memory caches
        for garage_id, address, name in valid_garages:
            address_normalized = address.lower()
            cache_key = (coords_key, address_normalized)
            
            # Check distance cache first (fastest path)
            if cache_key in _distance_cache:
                distance = _distance_cache[cache_key]
                memory_cache_hits += 1
                
                # Look for coordinates in memory caches
                garage_coords = None
                
                # Check expiry cache first
                if address_normalized in _geocode_cache_with_expiry:
                    cache_entry = _geocode_cache_with_expiry[address_normalized]
                    if cache_entry["expires_at"] > current_time:
                        garage_coords = cache_entry["coords"]
                
                # Then check regular cache
                if garage_coords is None and address_normalized in _geocode_cache:
                    garage_coords = _geocode_cache[address_normalized]
                
                # Calculate travel time
                travel_time_minutes = round((distance / 30) * 60)
                
                # Add to results
                result[garage_id] = {
                    "id": garage_id,
                    "address": address,
                    "name": name,
                    "distance": distance,
                    "travel_time_minutes": travel_time_minutes,
                    "coordinates": garage_coords
                }
                
                # Mark as processed
                processed_garages[address_normalized] = True
                
                # Background task to update Redis (don't wait for it)
                if garage_coords:
                    asyncio.create_task(_update_redis_coords(address_normalized, garage_coords))
            else:
                # Need to check other sources
                need_redis_check.append((garage_id, address, address_normalized, name))
        
        # Phase 2: Batch check Redis for remaining garages
        if need_redis_check:
            # Prepare Redis keys for batch retrieval
            redis_keys = [f"{REDIS_GEOCODE_PREFIX}{addr_norm}" for _, _, addr_norm, _ in need_redis_check]
            
            # Batch get from Redis
            try:
                # Get keys in parallel with an overall timeout
                redis_results = await asyncio.gather(*[redis_client.get(key) for key in redis_keys], 
                                                   return_exceptions=True)
                
                # Process Redis results
                for i, (garage_id, address, address_normalized, name) in enumerate(need_redis_check):
                    if i < len(redis_results):
                        redis_result = redis_results[i]
                        
                        # Skip errors from Redis
                        if isinstance(redis_result, Exception):
                            need_geocoding.append((garage_id, address, address_normalized, name))
                            continue
                            
                        # Process valid Redis result
                        if redis_result:
                            redis_hits += 1
                            coords = tuple(redis_result) if isinstance(redis_result, list) else redis_result
                            
                            # Calculate distance
                            try:
                                distance = calculate_distance_haversine(
                                    lat, lng, coords[0], coords[1]
                                )
                                distance = round(distance, 2)
                                
                                # Update memory caches
                                _distance_cache[(coords_key, address_normalized)] = distance
                                _geocode_cache[address_normalized] = coords
                                _geocode_cache_with_expiry[address_normalized] = {
                                    "coords": coords,
                                    "expires_at": current_time + REDIS_GEOCODE_EXPIRY
                                }
                                
                                # Calculate travel time
                                travel_time_minutes = round((distance / 30) * 60)
                                
                                # Add to results
                                result[garage_id] = {
                                    "id": garage_id,
                                    "address": address,
                                    "name": name,
                                    "distance": distance,
                                    "travel_time_minutes": travel_time_minutes,
                                    "coordinates": coords
                                }
                                
                                # Mark as processed
                                processed_garages[address_normalized] = True
                            except Exception as e:
                                logger.error(f"Error calculating distance for '{address}' from Redis coords: {str(e)}")
                                need_geocoding.append((garage_id, address, address_normalized, name))
                        else:
                            # No data in Redis
                            need_geocoding.append((garage_id, address, address_normalized, name))
                    else:
                        # Redis result missing
                        need_geocoding.append((garage_id, address, address_normalized, name))
            except Exception as e:
                logger.warning(f"Error in batch Redis operation: {str(e)}")
                # Add all to geocoding list if Redis batch fails
                need_geocoding.extend(need_redis_check)
        
        # Phase 3: Geocode remaining garages in optimized batches
        if need_geocoding:
            api_calls = len(need_geocoding)
            
            # Prepare geocoding tasks
            geocode_tasks = [geocode_address(addr) for _, addr, _, _ in need_geocoding]
            
            # Execute geocoding in parallel with timeout protection
            try:
                geocode_results = await asyncio.gather(*geocode_tasks, return_exceptions=True)
                
                # Process geocoding results
                for j, (garage_id, address, address_normalized, name) in enumerate(need_geocoding):
                    if j < len(geocode_results) and not isinstance(geocode_results[j], Exception) and geocode_results[j]:
                        coords = geocode_results[j]
                        
                        # Calculate distance
                        try:
                            distance = calculate_distance_haversine(
                                lat, lng, coords[0], coords[1]
                            )
                            distance = round(distance, 2)
                            
                            # Update caches
                            _distance_cache[(coords_key, address_normalized)] = distance
                            
                            # Calculate travel time
                            travel_time_minutes = round((distance / 30) * 60)
                            
                            # Add to results
                            result[garage_id] = {
                                "id": garage_id,
                                "address": address,
                                "name": name,
                                "distance": distance,
                                "travel_time_minutes": travel_time_minutes,
                                "coordinates": coords
                            }
                            
                            # Background task to update Redis (don't wait for it)
                            asyncio.create_task(_update_redis_coords(address_normalized, coords))
                        except Exception as e:
                            logger.error(f"Error calculating distance for '{address}': {str(e)}")
                    else:
                        error = geocode_results[j] if j < len(geocode_results) and isinstance(geocode_results[j], Exception) else "Unknown error"
                        logger.warning(f"Error geocoding address '{address}': {error}")
            except Exception as e:
                logger.error(f"Error during geocoding batch: {str(e)}")
        
        # Return sorted results
        if result:
            return dict(sorted(result.items(), key=lambda item: item[1]['distance']))
        return {}
    
    except Exception as e:
        logger.error(f"Error in find_nearby_garages: {str(e)}")
        return result
    finally:
        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"find_nearby_garages executed in {execution_time:.2f} seconds. Found {len(result)} garages. Memory cache hits: {memory_cache_hits}, Redis hits: {redis_hits}, API calls: {api_calls}")

# Helper function to update Redis in the background
async def _update_redis_coords(address_normalized: str, coords):
    """Update Redis with coordinates without blocking the main flow"""
    try:
        redis_key = f"{REDIS_GEOCODE_PREFIX}{address_normalized}"
        coords_list = list(coords) if isinstance(coords, tuple) else coords
        await redis_client.set(redis_key, coords_list, expiry=REDIS_GEOCODE_EXPIRY)
    except Exception as e:
        logger.warning(f"Background Redis update failed for {address_normalized}: {str(e)}")
        # Silently fail - this is a background optimization that shouldn't affect the main flow



async def calculate_distances_batch_from_coords_v2(lat: float, lng: float, addresses: list, token: str) -> dict:
    """
    Tính khoảng cách từ một tọa độ đến nhiều địa chỉ gara trong một lần gọi
    
    Args:
        lat: Vĩ độ
        lng: Kinh độ
        addresses: Danh sách các địa chỉ cần tính khoảng cách
        
    Returns:
        Dictionary với key là địa chỉ và value là thông tin gara bao gồm:
        - distance: Khoảng cách từ người dùng đến gara (km)
        - travel_time_minutes: Thời gian di chuyển ước tính (phút)
        - coords: Tọa độ (latitude, longitude) của gara
        - id: ID của gara
    """
    result = {}
    
    # Tạo key cho tọa độ người dùng
    coords_key = f"{lat:.6f},{lng:.6f}"
    current_time = time.time()

    # Danh sách địa chỉ cần tìm tọa độ (không có trong cache khoảng cách)
    need_coords = []
    
    # BƯỚC 1: Kiểm tra cache khoảng cách và phân loại địa chỉ
    
    
    try:
        # 1.1. Kiểm tra cache khoảng cách trước
        for address_data in addresses:
            address = address_data.get('address', '')
            garage_id = address_data.get('id')
            
            # Bỏ qua địa chỉ trống
            if not address:
                result[address if address else f"empty_{garage_id}"] = {
                    "distance": 0.0,
                    "travel_time_minutes": 0,
                    "coords": (0, 0),
                    "id": garage_id,
                }
                continue
            
            # Chuẩn hóa địa chỉ
            address_normalized = address.strip().lower()
            cache_key = (coords_key, address_normalized)
            
            # Kiểm tra cache khoảng cách
            if cache_key in _distance_cache:
                cache_data = _distance_cache[cache_key]
                distance = cache_data.get("distance", 0.0)
                coords = cache_data.get("coords", (0, 0))
                
                # Tính thời gian di chuyển bằng xe máy (phút) với tốc độ trung bình 30 km/h
                travel_time_minutes = round((distance / 30) * 60) if distance > 0 else 0
                
                # Lưu kết quả
                result[address] = {
                    "distance": distance,
                    "travel_time_minutes": travel_time_minutes,
                    "coords": coords,
                    "id": garage_id,
                }
            else:
                # Thêm vào danh sách cần tìm tọa độ
                need_coords.append({
                    "address": address,
                    "address_normalized": address_normalized,
                    "garage_id": garage_id,
                })
        
        # BƯỚC 2: Xử lý các địa chỉ cần tìm tọa độ (theo từng bước)
        if need_coords:
            # Lưu các địa chỉ cần xử lý sau mỗi bước
            remaining_after_expiry_cache = []
            remaining_after_regular_cache = []
            remaining_after_db_query = []
            garages_by_id = {}
            
            # BƯỚC 2.1: Tìm tọa độ từ cache có thời hạn
            for garage in need_coords:
                address = garage["address"]
                address_normalized = garage["address_normalized"]
                garage_id = garage["garage_id"]
                
                # Kiểm tra cache có thời hạn
                if address_normalized in _geocode_cache_with_expiry:
                    cache_entry = _geocode_cache_with_expiry[address_normalized]
                    if cache_entry["expires_at"] > current_time:
                        # Tìm thấy tọa độ trong cache có thời hạn
                        coords = cache_entry["coords"]
                        
                        # Tính khoảng cách
                        if coords and coords != (0, 0):
                            distance = calculate_distance_haversine(lat, lng, coords[0], coords[1])
                            distance = round(distance, 2)
                            travel_time_minutes = round((distance / 30) * 60)
                        else:
                            distance = 0.0
                            travel_time_minutes = 0
                        
                        # Lưu kết quả
                        result[address] = {
                            "distance": distance,
                            "travel_time_minutes": travel_time_minutes,
                            "coords": coords,
                            "id": garage_id,
                        }
                        
                        # Lưu vào cache khoảng cách
                        _distance_cache[(coords_key, address_normalized)] = {
                            "distance": distance,
                            "coords": coords
                        }
                    else:
                        # Cache hết hạn, xóa và tiếp tục xử lý
                        del _geocode_cache_with_expiry[address_normalized]
                        remaining_after_expiry_cache.append(garage)
                else:
                    # Không có trong cache có thời hạn tìm tọa độ từ cache thông thường
                    if address_normalized in _geocode_cache:
                        coords = _geocode_cache[address_normalized]
                        # Cập nhật cache có thời hạn
                        if coords:
                            expires_at = current_time + (30 * 24 * 60 * 60)  # 30 days
                            _geocode_cache_with_expiry[address_normalized] = {
                                "coords": coords,
                                "expires_at": expires_at
                            }
                        # Tính khoảng cách
                        if coords and coords != (0, 0):
                            distance = calculate_distance_haversine(lat, lng, coords[0], coords[1])
                            distance = round(distance, 2)
                            travel_time_minutes = round((distance / 30) * 60)
                        else:
                            distance = 0.0
                            travel_time_minutes = 0
                        # Lưu kết quả
                        result[address] = {
                            "distance": distance,
                            "travel_time_minutes": travel_time_minutes,
                            "coords": coords,
                            "id": garage_id,
                        }
                        # Lưu vào cache khoảng cách
                        _distance_cache[(coords_key, address_normalized)] = {
                            "distance": distance,
                            "coords": coords
                        }
                    else:
                        # Không có trong cache thông thường
                        remaining_after_regular_cache.append(garage)
                        # Nhóm các gara theo ID để tối ưu truy vấn
                        if garage_id is not None:
                            garages_by_id[garage_id] = garage
            
            # BƯỚC 2.2: Truy vấn tọa độ từ database
            # Xử lý theo batch để tránh quá nhiều kết nối DB
            if remaining_after_regular_cache:
                # Nhóm các gara theo ID để tối ưu truy vấn
                
                # Chỉ truy vấn DB nếu có ID gara hợp lệ
                if garages_by_id:
                    try:
                        # Truy vấn hàng loạt từ database
                        # Tạo điều kiện IN cho query
                        garage_ids = list(garages_by_id.keys())
                        
                        # Tạo placeholders dạng $1, $2, $3, ...
                        placeholders = ', '.join([f'${i+1}' for i in range(len(garage_ids))])
                        
                        # Tạo query với placeholders dạng $1, $2, ...
                        query = f"SELECT id, latitude, longitude FROM res_partner_gara WHERE id IN ({placeholders})"
                        
                        # Truyền danh sách các giá trị trực tiếp, không cần dictionary
                        db_results = await PostgresDB.execute_query(query, garage_ids)
                        
                        # Xử lý kết quả từ database
                        for row in db_results:
                            garage_id, lat_db, lng_db = row
                            
                            # Kiểm tra nếu tọa độ hợp lệ
                            if garage_id in garages_by_id and lat_db and lng_db and lat_db != 0 and lng_db != 0:
                                garage = garages_by_id[garage_id]
                                address = garage["address"]
                                address_normalized = garage["address_normalized"]
                                
                                coords = (lat_db, lng_db)
                                
                                # Cập nhật caches
                                _geocode_cache[address_normalized] = coords
                                _geocode_cache_with_expiry[address_normalized] = {
                                    "coords": coords,
                                    "expires_at": current_time + (30 * 24 * 60 * 60)
                                }
                                
                                # Tính khoảng cách
                                distance = calculate_distance_haversine(lat, lng, coords[0], coords[1])
                                distance = round(distance, 2)
                                travel_time_minutes = round((distance / 30) * 60)
                                
                                # Lưu kết quả
                                result[address] = {
                                    "distance": distance,
                                    "travel_time_minutes": travel_time_minutes,
                                    "coords": coords,
                                    "id": garage_id,
                                }
                                
                                # Lưu vào cache khoảng cách
                                _distance_cache[(coords_key, address_normalized)] = {
                                    "distance": distance,
                                    "coords": coords
                                }
                                
                                # Đánh dấu gara đã xử lý để không tìm kiếm trên API
                                del garages_by_id[garage_id]
                        
                        # Các gara còn lại cần tìm trên API
                        for garage_id, garage in garages_by_id.items():
                            remaining_after_db_query.append(garage)
                        
                    except Exception as e:
                        logger.error(f"Lỗi khi truy vấn tọa độ từ database: {str(e)}")
                        # Nếu có lỗi, thêm tất cả các gara chưa xử lý vào danh sách tiếp theo
                        remaining_after_db_query.extend(list(garages_by_id.values()))
                else:
                    # Không có ID gara hợp lệ, thêm tất cả vào danh sách tiếp theo
                    remaining_after_db_query.extend(remaining_after_regular_cache)
            
            # BƯỚC 2.4: Sử dụng Here Maps API cho các địa chỉ còn lại
            if remaining_after_db_query:
                geocode_tasks = [here_maps_geocode_with_api(garage, lat, lng, token) for garage in remaining_after_db_query]
                geocode_results = await asyncio.gather(*geocode_tasks, return_exceptions=True)
                for result_item in geocode_results:
                    if isinstance(result_item, Exception):
                        logger.error(f"Lỗi khi geocode: {str(result_item)}")
                        continue
                    
                    if result_item:
                        address = result_item["address"]
                        result[address] = {
                            "distance": result_item["distance"],
                            "travel_time_minutes": result_item["travel_time_minutes"],
                            "coords": result_item["coords"],
                            "id": result_item["id"],
                        }
                        
    except Exception as e:
        logger.error(f"Lỗi trong quá trình tính khoảng cách: {str(e)}")
    
    # Trả về kết quả được sắp xếp theo khoảng cách
    return dict(sorted(result.items(), key=lambda item: item[1]['distance']))

# Hàm helper để tìm tọa độ thông qua API
async def here_maps_geocode_with_api(garage, lat, lng, token):
    """
    Tìm tọa độ cho một địa chỉ gara sử dụng Here Maps API
    
    Args:
        garage: Dictionary chứa thông tin gara
        
    Returns:
        Dictionary chứa kết quả hoặc None nếu lỗi
    """
    address = garage["address"]
    address_normalized = garage["address_normalized"]
    garage_id = garage["garage_id"]
    
    try:
        # Sử dụng Here Maps Geocoding API
        api_key = settings.HERE_MAPS_API_KEY
        url = f"{HERE_MAPS_URL}?q={address}&apiKey={api_key}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            
            if data["items"]:
                location = data["items"][0]["position"]
                coords = (location["lat"], location["lng"])
                
                # Lưu vào cache
                _geocode_cache[address_normalized] = coords
                _geocode_cache_with_expiry[address_normalized] = {
                    "coords": coords,
                    "expires_at": time.time() + (30 * 24 * 60 * 60)
                }
                
                # Cập nhật DB trong background task
                if garage_id:
                    asyncio.create_task(update_orm_coords(garage_id, coords, token))
                
                # Tính khoảng cách
                
                
                distance = calculate_distance_haversine(lat, lng, coords[0], coords[1])
                distance = round(distance, 2)
                travel_time_minutes = round((distance / 30) * 60)
                
                # Lưu vào cache khoảng cách
                coords_key = f"{lat:.6f},{lng:.6f}"
                _distance_cache[(coords_key, address_normalized)] = {
                    "distance": distance,
                    "coords": coords
                }
                
                return {
                    "address": address,
                    "distance": distance,
                    "travel_time_minutes": travel_time_minutes,
                    "coords": coords,
                    "id": garage_id,
                    "api_used": True
                }
            else:
                # Lưu None vào cache để tránh gọi lại API cho địa chỉ không hợp lệ
                _geocode_cache[address_normalized] = None
                return {
                    "address": address,
                    "distance": 0.0,
                    "travel_time_minutes": 0,
                    "coords": (0, 0),
                    "id": garage_id,
                    "api_used": True
                }
    except Exception as e:
        logger.error(f"Lỗi khi geocode địa chỉ {address}: {str(e)}")
        return None

# Hàm helper để cập nhật tọa độ vào database
async def update_orm_coords(garage_id, coords, token):
    """
    Cập nhật tọa độ gara vào database
    
    Args:
        garage_id: ID của gara
        coords: Tuple (latitude, longitude)
    """
    try:
        response = await odoo.call_method_post(
        record_id=garage_id,
        model='res.partner.gara',
        method='update_coordinates_from_api',
        token=token,
        kwargs={'latitude': coords[0], 'longitude': coords[1]}
        )
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật tọa độ qua orm: garage_id={garage_id}, lỗi={str(e)}")
