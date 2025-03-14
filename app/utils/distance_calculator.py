import httpx
import logging
import math
import json
from typing import Tuple, Optional, Dict
from ..config import settings
from functools import lru_cache
import asyncio
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Cache cho các tọa độ đã được geocode
_geocode_cache = {}

# Cache cho các tọa độ đã được geocode với thời gian hết hạn (1 tháng)
# Format: {address_normalized: {"coords": (lat, lng), "expires_at": timestamp}}
_geocode_cache_with_expiry = {}

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
        # Sử dụng Google Maps Geocoding API
        api_key = settings.GOOGLE_MAPS_API_KEY
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
        
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

async def find_nearby_garages(lat: float, lng: float, garage_list: list, radius_km: float = 20.0, batch_size: int = 50, max_results: int = 100) -> dict:
    """
    Tìm các gara sửa chữa trong phạm vi bán kính cho trước từ vị trí người dùng
    
    Args:
        lat: Vĩ độ của người dùng
        lng: Kinh độ của người dùng
        garage_list: Danh sách các gara cần kiểm tra, mỗi phần tử là một dict chứa thông tin gara
                    với ít nhất trường 'id' và 'address'
        radius_km: Bán kính tìm kiếm tính bằng km (mặc định là 20km)
        batch_size: Số lượng gara xử lý trong mỗi batch (mặc định là 50)
        max_results: Số lượng kết quả tối đa trả về (mặc định là 100)
        
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
    current_time = time.time()
    cache_hits = 0
    cache_misses = 0
    
    try:
        # Validate input parameters
        if not isinstance(garage_list, list):
            logger.error("garage_list must be a list")
            return {}
            
        if not (isinstance(lat, (int, float)) and isinstance(lng, (int, float))):
            logger.error("lat and lng must be numeric values")
            return {}
            
        # Tạo key cho tọa độ người dùng
        coords_key = f"{lat:.6f},{lng:.6f}"
        
        # Lọc ra các gara có địa chỉ hợp lệ
        valid_garages = []
        for garage in garage_list:
            if not isinstance(garage, dict):
                continue
                
            garage_id = garage.get('id')
            address = garage.get('address', '').strip() if garage.get('address') else ''
            name = garage.get('name', '').strip() if garage.get('name') else ''
            
            if garage_id and address and name:
                valid_garages.append((garage_id, address, name))
        
        logger.debug(f"Found {len(valid_garages)} valid garages out of {len(garage_list)} total")
        
        # Kiểm tra cache trước và tách thành hai danh sách: đã có trong cache và chưa có trong cache
        cached_garages = []
        uncached_garages = []
        
        for garage_id, address, name in valid_garages:
            address_normalized = address.lower()
            cache_key = (coords_key, address_normalized)
            
            # Kiểm tra xem đã có tọa độ của gara trong cache có thời hạn chưa
            garage_coords = None
            if address_normalized in _geocode_cache_with_expiry:
                cache_entry = _geocode_cache_with_expiry[address_normalized]
                if cache_entry["expires_at"] > current_time:
                    garage_coords = cache_entry["coords"]
            
            # Nếu không có trong cache có thời hạn, kiểm tra cache thông thường
            if garage_coords is None and address_normalized in _geocode_cache:
                garage_coords = _geocode_cache[address_normalized]
                # Nếu tìm thấy trong cache thông thường, cập nhật vào cache có thời hạn
                if garage_coords is not None:
                    expires_at = current_time + (30 * 24 * 60 * 60)  # 30 days in seconds
                    _geocode_cache_with_expiry[address_normalized] = {
                        "coords": garage_coords,
                        "expires_at": expires_at
                    }
            
            if cache_key in _distance_cache:
                distance = _distance_cache[cache_key]
                # Chỉ thêm vào danh sách nếu nằm trong bán kính
                if distance <= radius_km:
                    cached_garages.append((garage_id, address, address_normalized, distance, name, garage_coords))
                    cache_hits += 1
            else:
                uncached_garages.append((garage_id, address, address_normalized, name))
                cache_misses += 1
        
        logger.debug(f"Cache hits: {cache_hits}, Cache misses: {cache_misses}")
        
        # Xử lý các gara đã có trong cache trước
        for garage_id, address, address_normalized, distance, name, coords in cached_garages:
            # Tính thời gian di chuyển
            travel_time_minutes = round((distance / 30) * 60)
            
            result[garage_id] = {
                "id": garage_id,
                "address": address,
                "name": name,
                "distance": distance,
                "travel_time_minutes": travel_time_minutes,
                "coordinates": coords
            }
            
            # Nếu đã đủ số lượng kết quả tối đa, dừng xử lý
            if len(result) >= max_results:
                logger.debug(f"Reached max_results ({max_results}) from cached garages")
                return dict(sorted(result.items(), key=lambda item: item[1]['distance']))
        
        # Xử lý các gara chưa có trong cache theo batch
        if uncached_garages:
            # Chia thành các batch để xử lý
            for i in range(0, len(uncached_garages), batch_size):
                batch = uncached_garages[i:i+batch_size]
                
                # Geocode tất cả các địa chỉ trong batch cùng một lúc
                geocode_tasks = []
                for _, addr, _, _ in batch:
                    geocode_tasks.append(geocode_address(addr))
                
                # Sử dụng timeout để tránh treo quá lâu
                try:
                    geocode_results = await asyncio.gather(*geocode_tasks, return_exceptions=True)
                except Exception as e:
                    logger.error(f"Error during geocoding batch: {str(e)}")
                    continue
                
                # Tính khoảng cách cho từng gara trong batch
                for j, (garage_id, address, address_normalized, name) in enumerate(batch):
                    if j >= len(geocode_results):
                        continue
                        
                    coords_result = geocode_results[j]
                    
                    # Kiểm tra nếu có lỗi trong kết quả
                    if isinstance(coords_result, Exception):
                        logger.warning(f"Error geocoding address '{address}': {str(coords_result)}")
                        continue
                    
                    coords = coords_result
                    if coords:
                        # Lưu tọa độ vào cache có thời hạn (1 tháng)
                        expires_at = current_time + (30 * 24 * 60 * 60)  # 30 days in seconds
                        _geocode_cache_with_expiry[address_normalized] = {
                            "coords": coords,
                            "expires_at": expires_at
                        }
                        
                        # Tính khoảng cách
                        try:
                            distance = calculate_distance_haversine(
                                lat, lng,
                                coords[0], coords[1]
                            )
                            distance = round(distance, 2)
                        except Exception as e:
                            logger.error(f"Error calculating distance for '{address}': {str(e)}")
                            continue

                        # Lưu vào cache
                        cache_key = (coords_key, address_normalized)
                        _distance_cache[cache_key] = distance

                        # Chỉ thêm vào kết quả nếu nằm trong bán kính
                        if distance <= radius_km:
                            # Tính thời gian di chuyển bằng xe máy (phút) với tốc độ trung bình 30 km/h
                            travel_time_minutes = round((distance / 30) * 60)

                            result[garage_id] = {
                                "id": garage_id,
                                "address": address,
                                "name": name,
                                "distance": distance,
                                "travel_time_minutes": travel_time_minutes,
                                "coordinates": coords
                            }
                            
                            # Nếu đã đủ số lượng kết quả tối đa, dừng xử lý
                            if len(result) >= max_results:
                                logger.debug(f"Reached max_results ({max_results}) during batch processing")
                                # Sắp xếp kết quả theo khoảng cách tăng dần
                                return dict(sorted(result.items(), key=lambda item: item[1]['distance']))
        
        # Sắp xếp kết quả theo khoảng cách tăng dần
        sorted_result = dict(sorted(result.items(), key=lambda item: item[1]['distance']))
        
        # Giới hạn số lượng kết quả
        if len(sorted_result) > max_results:
            # Chuyển thành list để cắt và sau đó chuyển lại thành dict
            sorted_items = list(sorted_result.items())[:max_results]
            return dict(sorted_items)
        
        return sorted_result
    except Exception as e:
        logger.error(f"Error in find_nearby_garages: {str(e)}")
        return result
    finally:
        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"find_nearby_garages executed in {execution_time:.2f} seconds. Found {len(result)} garages within {radius_km}km radius. Cache hits: {cache_hits}, misses: {cache_misses}")

async def find_nearby_garages_by_addresses(lat: float, lng: float, garage_addresses: list, radius_km: float = 20.0) -> dict:
    """
    Tìm các gara sửa chữa trong phạm vi bán kính cho trước từ vị trí người dùng dựa trên danh sách địa chỉ
    
    Args:
        lat: Vĩ độ của người dùng
        lng: Kinh độ của người dùng
        garage_addresses: Danh sách các địa chỉ gara cần kiểm tra
        radius_km: Bán kính tìm kiếm tính bằng km (mặc định là 20km)
        
    Returns:
        Dictionary với key là địa chỉ gara và value là thông tin gara bao gồm:
        - address: Địa chỉ gara
        - distance: Khoảng cách từ vị trí người dùng đến gara (km)
        - travel_time_minutes: Thời gian di chuyển bằng xe máy (phút)
        - coordinates: Tọa độ của gara (lat, lng)
        - is_within_radius: True nếu nằm trong bán kính, False nếu không
    """
    # Tính khoảng cách đến tất cả các địa chỉ gara
    distances = await calculate_distances_batch_from_coords(lat, lng, garage_addresses)
    
    result = {}
    
    # Lọc và định dạng kết quả
    for address, distance_info in distances.items():
        if not address:
            continue
            
        distance = distance_info["distance"]
        travel_time_minutes = distance_info["travel_time_minutes"]
        
        # Lấy tọa độ của gara từ cache nếu có
        address_normalized = address.strip().lower()
        garage_coords = _geocode_cache.get(address_normalized)
        
        result[address] = {
            "address": address,
            "distance": distance,
            "travel_time_minutes": travel_time_minutes,
            "coordinates": garage_coords,
            "is_within_radius": distance <= radius_km
        }
    
    # Sắp xếp kết quả theo khoảng cách tăng dần
    sorted_result = dict(sorted(result.items(), key=lambda item: item[1]['distance']))
    
    return sorted_result 