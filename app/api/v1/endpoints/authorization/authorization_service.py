from fastapi import APIRouter, Header, Depends, Body, HTTPException, status
from typing import Optional
import logging
import random
from app.config import settings, odoo
from app.utils.erp_db import PostgresDB
from app.utils.redis_client import redis_client as redis_client_instance

import jwt
import datetime
from datetime import timedelta
from app.config import settings
from app.api.deps import get_token_key

REDIS_EXPIRE = 2592000
OTP_EXPIRE = 180  # 3 phút
OTP_REDIS_PREFIX = "otp:"
OTP_RATE_LIMIT_PREFIX = "otp_rate_limit:"

logger = logging.getLogger(__name__)

class AuthorizationService:

    @classmethod
    async def create_token(cls, user: dict):
        """
        Sinh JWT token cho user và lưu vào Redis với TTL 30 ngày
        """
        payload = {
            "token": user["token"],
            "uid": user["uid"],
            'partner_id': user["partner_id"],
            "iat": datetime.datetime.now() - timedelta(hours=7),
            "exp": datetime.datetime.now() + timedelta(days=30)
        }

        # Tạo JWT token
        token = jwt.encode(payload, settings.TOKEN_PREFIX, algorithm="HS256")

        # Lưu vào Redis
        redis_key = get_token_key(token)
        await redis_client_instance.set(redis_key, f"login:{user['login']}")
        await redis_client_instance.expire(redis_key, REDIS_EXPIRE)

        return token


    @classmethod
    async def register_user_portal(cls, data: dict):

        user  = await cls.check_user_info_exits(data)
        if user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Số điện thoại của bạn đã tồn tại"
            )
        await odoo.call_method_not_record(
            model='res.users',
            method='create_users_portal',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )

        return {
            "success": True,
            "message": "Registration successful",
            "data": {
                "user": data
            }
        }

    @classmethod
    async def check_user_info_exits(cls, data: dict):
        sql = f"""
        select id, login from res_users where login = '{data['phone']}'
                  """
        result = {}
        user_data = await PostgresDB.execute_query(sql)
        if user_data:
            result = {
                'id': user_data[0].get('id'),
                'name': user_data[0].get('name'),
            }
        return result



    @classmethod
    async def get_device_by_phone_user(cls, data: dict):
        phone = data['phone']
        device_id = data['device_id']

        sql = f"""
                SELECT ru.id AS uid, ru.login, rp.name, ru.token, ru.partner_id
                FROM res_users_device rud
                JOIN res_users ru ON rud.user_id = ru.id
                join res_partner rp on ru.partner_id = rp.id
                WHERE ru.login = '{phone}' AND rud.device_id = '{device_id}'
            """

        device_data = await PostgresDB.execute_query(sql)

        # Nếu tồn tại device + phone
        if device_data and len(device_data) > 0:
            user = device_data[0]
            data = {
                'token': user.get('token'),
                'uid': user.get('uid'),
                'login': user.get('login'),
                'partner_id': user.get('partner_id'),
            }
            token = await cls.create_token(data)

            return {
                "success": True,
                "message": "Login successful",
                "data": {
                    "token": token,
                    "phone": phone
                }
            }

        # Nếu không tồn tại
        return {
            "success": False,
            "message": "Device or phone not found",
            "data": None
        }

    @classmethod
    async def login_user(cls, data: dict):
        try:
            logger.info(f"AuthorizationService.login_user called with data: {data}")
            phone = data['phone']
            password = data['password']
            logger.info(f"Attempting to authenticate phone: {phone}")
            
            res = await odoo.authenticate(phone, password)
            logger.info(f"Odoo authentication result: {res}")
            
            token = await cls.create_token(res)
            logger.info(f"Token created successfully")
            
            await cls.create_update_device_id(data)
            logger.info(f"Device ID updated successfully")
            
            return {
                "success": True,
                "message": "Login successful",
                "data": {
                    "token": token,
                    "phone": phone
                }
            }
        except Exception as e:
            logger.error(f"Error in login_user: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    @classmethod
    async def create_update_device_id(cls, data: dict):
        await odoo.call_method_not_record(
            model='res.users',
            method='create_update_device_id',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )
        return True

    @classmethod
    async def check_otp_rate_limit(cls, phone: str, client_ip: str = None):
        """
        Kiểm tra rate limit cho việc gửi OTP
        - 1 số điện thoại: tối đa 3 lần / 5 phút, tối đa 5-6 lần / 24 giờ
        - 1 IP: tối đa 10-20 request / phút
        """
        # Check rate limit cho phone: 3 lần / 5 phút
        phone_5min_key = f"{OTP_RATE_LIMIT_PREFIX}phone:{phone}:5min"
        phone_5min_count = await redis_client_instance.get(phone_5min_key)
        phone_5min_count = int(phone_5min_count) if phone_5min_count else 0
        
        if phone_5min_count >= 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Bạn đã gửi quá nhiều mã OTP. Vui lòng đợi 5 phút trước khi thử lại."
            )
        
        # Check rate limit cho phone: 5-6 lần / 24 giờ
        phone_24h_key = f"{OTP_RATE_LIMIT_PREFIX}phone:{phone}:24h"
        phone_24h_count = await redis_client_instance.get(phone_24h_key)
        phone_24h_count = int(phone_24h_count) if phone_24h_count else 0
        
        if phone_24h_count >= 6:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Bạn đã vượt quá số lần gửi OTP trong ngày. Vui lòng thử lại sau 24 giờ."
            )
        
        # Check rate limit cho IP: 15 request / phút (chọn giữa 10-20)
        if client_ip:
            ip_1min_key = f"{OTP_RATE_LIMIT_PREFIX}ip:{client_ip}:1min"
            ip_1min_count = await redis_client_instance.get(ip_1min_key)
            ip_1min_count = int(ip_1min_count) if ip_1min_count else 0
            
            if ip_1min_count >= 15:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Quá nhiều yêu cầu từ IP này. Vui lòng đợi 1 phút trước khi thử lại."
                )
        
        # Tăng counter (chỉ set expiry lần đầu khi key mới được tạo)
        await redis_client_instance.incr(phone_5min_key, expiry=300)  # 5 phút
        await redis_client_instance.incr(phone_24h_key, expiry=86400)  # 24 giờ
        
        if client_ip:
            await redis_client_instance.incr(ip_1min_key, expiry=60)  # 1 phút
        
        return True

    @classmethod
    async def send_otp(cls, data: dict, client_ip: str = None):
        """
        Gửi mã OTP qua ZNS và lưu vào Redis
        """
        try:
            phone = data.get('phone')
            if not phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Số điện thoại không được để trống"
                )
            
            # Kiểm tra rate limit
            await cls.check_otp_rate_limit(phone, client_ip)
            
            # Tạo mã OTP 6 chữ số, đảm bảo không có số 0 ở đầu
            # Chữ số đầu tiên: 1-9, các chữ số còn lại: 0-9
            first_digit = random.randint(1, 9)  # Chữ số đầu không được là 0
            remaining_digits = ''.join([str(random.randint(0, 9)) for _ in range(5)])
            otp_code = str(first_digit) + remaining_digits
            
            # Gửi OTP qua Odoo (sẽ gọi ZNS)
            try:
                result = await odoo.call_method_not_record(
                    model='zalo.notification',
                    method='send_otp',
                    token=settings.ODOO_TOKEN,
                    kwargs={
                        'phone': phone,
                        'otp_code': otp_code
                    }
                )
                
                # Kiểm tra kết quả từ Odoo
                # result có thể là False hoặc dict
                if result is False or (isinstance(result, dict) and result.get('error') != 0):
                    logger.error(f"Không thể gửi OTP qua ZNS. Result: {result}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Không thể gửi mã OTP. Vui lòng thử lại sau."
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Lỗi khi gửi OTP qua Odoo: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Không thể gửi mã OTP. Vui lòng thử lại sau."
                )
            
            # Lưu OTP vào Redis với key là phone và TTL 3 phút
            redis_key = f"{OTP_REDIS_PREFIX}{phone}"
            await redis_client_instance.set(redis_key, str(otp_code), expiry=OTP_EXPIRE)
            
            logger.info(f"Đã gửi OTP thành công cho số điện thoại: {phone}")
            
            return {
                "success": True,
                "message": "Mã OTP đã được gửi thành công",
                "data": {
                    "phone": phone,
                    "expiry_seconds": OTP_EXPIRE
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Lỗi trong send_otp: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi hệ thống: {str(e)}"
            )

    @classmethod
    async def verify_otp(cls, data: dict):
        """
        Xác thực mã OTP từ Redis và tự động login nếu user tồn tại
        """
        try:
            phone = data.get('phone')
            otp_code = data.get('otp_code')
            device_id = data.get('device_id')  # Optional, để update device sau khi login
            
            if not phone or not otp_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Số điện thoại và mã OTP không được để trống"
                )
            
            # Lấy OTP từ Redis
            redis_key = f"{OTP_REDIS_PREFIX}{phone}"
            stored_otp = await redis_client_instance.get(redis_key)
            
            if not stored_otp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mã OTP không tồn tại hoặc đã hết hạn. Vui lòng yêu cầu mã mới."
                )
            
            # Đảm bảo stored_otp và otp_code đều là string để so sánh
            stored_otp = str(stored_otp).strip()
            otp_code = str(otp_code).strip()
            
            # So sánh OTP
            if stored_otp != otp_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mã OTP không chính xác"
                )
            
            # Xóa OTP sau khi xác thực thành công
            await redis_client_instance.delete(redis_key)
            
            logger.info(f"Xác thực OTP thành công cho số điện thoại: {phone}")
            
            # Kiểm tra xem user có tồn tại không (tương tự như get_device_by_phone_user)
            sql = f"""
                    SELECT ru.id AS uid, ru.login, rp.name, ru.token, ru.partner_id
                    FROM res_users ru
                    JOIN res_partner rp ON ru.partner_id = rp.id
                    WHERE ru.login = '{phone}'
                """
            
            user_data = await PostgresDB.execute_query(sql)
            
            # Nếu user tồn tại, tự động login
            if user_data and len(user_data) > 0:
                user = user_data[0]
                user_info = {
                    'token': user.get('token'),
                    'uid': user.get('uid'),
                    'login': user.get('login'),
                    'partner_id': user.get('partner_id'),
                }
                
                # Tạo token
                token = await cls.create_token(user_info)
                
                # Update device_id nếu có
                if device_id:
                    try:
                        await cls.create_update_device_id({
                            'phone': phone,
                            'device_id': device_id
                        })
                    except Exception as e:
                        logger.warning(f"Không thể update device_id: {str(e)}")
                
                logger.info(f"Tự động login thành công cho số điện thoại: {phone}")
                
                return {
                    "success": True,
                    "message": "Xác thực OTP và đăng nhập thành công",
                    "data": {
                        "phone": phone,
                        "verified": True,
                        "token": token
                    }
                }
            
            # Nếu user không tồn tại, tự động tạo user mới
            logger.info(f"Xác thực OTP thành công nhưng user chưa tồn tại, đang tạo user mới: {phone}")
            
            try:
                # Tạo user mới với name mặc định (có thể dùng phone hoặc "Khách hàng")
                user_name = f"Khách hàng {phone}"
                
                # Gọi Odoo để tạo user
                await odoo.call_method_not_record(
                    model='res.users',
                    method='create_users_portal',
                    token=settings.ODOO_TOKEN,
                    kwargs={
                        'phone': phone,
                        'name': user_name
                    },
                )
                
                logger.info(f"Đã tạo user mới thành công: {phone}")
                
                # Sau khi tạo user, query lại để lấy thông tin user vừa tạo
                user_data = await PostgresDB.execute_query(sql)
                
                if user_data and len(user_data) > 0:
                    user = user_data[0]
                    user_info = {
                        'token': user.get('token'),
                        'uid': user.get('uid'),
                        'login': user.get('login'),
                        'partner_id': user.get('partner_id'),
                    }
                    
                    # Tạo token
                    token = await cls.create_token(user_info)
                    
                    # Update device_id nếu có
                    if device_id:
                        try:
                            await cls.create_update_device_id({
                                'phone': phone,
                                'device_id': device_id
                            })
                        except Exception as e:
                            logger.warning(f"Không thể update device_id: {str(e)}")
                    
                    logger.info(f"Tự động login thành công cho user mới: {phone}")
                    
                    return {
                        "success": True,
                        "message": "Xác thực OTP thành công và đã tạo tài khoản mới",
                        "data": {
                            "phone": phone,
                            "verified": True,
                            "token": token,
                            "new_user": True
                        }
                    }
                else:
                    # Nếu sau khi tạo vẫn không query được user, trả về lỗi
                    logger.error(f"Đã tạo user nhưng không thể query lại: {phone}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Đã tạo tài khoản nhưng không thể đăng nhập. Vui lòng thử lại."
                    )
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Lỗi khi tạo user mới: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Không thể tạo tài khoản mới: {str(e)}"
                )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Lỗi trong verify_otp: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi hệ thống: {str(e)}"
            )

    @classmethod
    async def zalo_miniapp_login(cls, data: dict):
        """
        API dành cho Zalo Mini App:
        - Tự động lấy zalo_id và phone từ Zalo SDK
        - Nếu user đã tồn tại (theo phone): tự động login
        - Nếu user chưa tồn tại: tạo user mới với phone, name, zalo_id rồi login
        """
        phone = data.get('phone')
        name = data.get('name')
        zalo_id = data.get('zalo_id')
        device_id = data.get('device_id')
        
        if not phone or not name or not zalo_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thiếu thông tin: phone, name, zalo_id là bắt buộc"
            )
        
        try:
            # Query user theo phone
            sql = f"""
                    SELECT ru.id AS uid, ru.login, rp.name, ru.token, ru.partner_id
                    FROM res_users ru
                    JOIN res_partner rp ON ru.partner_id = rp.id
                    WHERE ru.login = '{phone}' or  ru.zalo_id = '{zalo_id}'
                """
            
            user_data = await PostgresDB.execute_query(sql)
            
            # Nếu user tồn tại, tự động login
            if user_data and len(user_data) > 0:
                user = user_data[0]
                user_info = {
                    'token': user.get('token'),
                    'uid': user.get('uid'),
                    'login': user.get('login'),
                    'partner_id': user.get('partner_id'),
                }
                
                # Tạo token
                token = await cls.create_token(user_info)
                
                # Update device_id nếu có
                if device_id:
                    try:
                        await cls.create_update_device_id({
                            'phone': phone,
                            'device_id': device_id
                        })
                    except Exception as e:
                        logger.warning(f"Không thể update device_id: {str(e)}")
                
                logger.info(f"Zalo Mini App: Tự động login thành công cho số điện thoại: {phone}")
                
                return {
                    "success": True,
                    "message": "Đăng nhập thành công",
                    "data": {
                        "phone": phone,
                        "token": token,
                        "new_user": False
                    }
                }
            
            # Nếu user không tồn tại, tự động tạo user mới
            logger.info(f"Zalo Mini App: User chưa tồn tại, đang tạo user mới: {phone}, zalo_id: {zalo_id}")
            
            try:
                # Gọi Odoo để tạo user với phone, name, zalo_id
                await odoo.call_method_not_record(
                    model='res.users',
                    method='create_users_portal',
                    token=settings.ODOO_TOKEN,
                    kwargs={
                        'phone': phone,
                        'name': name,
                        'zalo_id': zalo_id
                    },
                )
                
                logger.info(f"Zalo Mini App: Đã tạo user mới thành công: {phone}")
                
                # Sau khi tạo user, query lại để lấy thông tin user vừa tạo
                user_data = await PostgresDB.execute_query(sql)
                
                if user_data and len(user_data) > 0:
                    user = user_data[0]
                    user_info = {
                        'token': user.get('token'),
                        'uid': user.get('uid'),
                        'login': user.get('login'),
                        'partner_id': user.get('partner_id'),
                    }
                    
                    # Tạo token
                    token = await cls.create_token(user_info)
                    
                    # Update device_id nếu có
                    if device_id:
                        try:
                            await cls.create_update_device_id({
                                'phone': phone,
                                'device_id': device_id
                            })
                        except Exception as e:
                            logger.warning(f"Không thể update device_id cho user mới: {str(e)}")
                    
                    logger.info(f"Zalo Mini App: Tự động login thành công cho user mới: {phone}")
                    
                    return {
                        "success": True,
                        "message": "Đã tạo tài khoản và đăng nhập thành công",
                        "data": {
                            "phone": phone,
                            "token": token,
                            "new_user": True
                        }
                    }
                else:
                    # Nếu sau khi tạo vẫn không query được user, trả về lỗi
                    logger.error(f"Zalo Mini App: Đã tạo user nhưng không thể query lại: {phone}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Đã tạo tài khoản nhưng không thể đăng nhập. Vui lòng thử lại."
                    )
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Zalo Mini App: Lỗi khi tạo user mới: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Không thể tạo tài khoản mới: {str(e)}"
                )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Zalo Mini App: Lỗi trong zalo_miniapp_login: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi hệ thống: {str(e)}"
            )
















