import httpx
import logging
import math
import json
from typing import Tuple, Optional, Dict
from ..config import settings
from functools import lru_cache
import asyncio

logger = logging.getLogger(__name__)

# Cache cho các tọa độ đã được geocode
_geocode_cache = {}

# Cache cho các khoảng cách đã được tính
_distance_cache = {}

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
    
    # Kiểm tra cache
    if normalized_address in _geocode_cache:
        return _geocode_cache[normalized_address]
        
    try:
        # Sử dụng Google Maps Geocoding API
        api_key = settings.GOOGLE_MAPS_API_KEY
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            
            if data["status"] == "OK" and data["results"]:
                location = data["results"][0]["geometry"]["location"]
                coords = (location["lat"], location["lng"])
                
                # Lưu vào cache
                _geocode_cache[normalized_address] = coords
                
                return coords
            else:
                logger.warning(f"Không thể geocode địa chỉ: {address}. Status: {data['status']}")
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
        
        # Chuyển đổi tuple key thành string để có thể serialize
        distance_cache_serializable = {}
        for key, value in _distance_cache.items():
            distance_cache_serializable[str(key)] = value
        
        cache_data = {
            "geocode_cache": geocode_cache_serializable,
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
        geocode_tasks = [geocode_address(addr) for addr, _ in addresses_to_geocode]
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