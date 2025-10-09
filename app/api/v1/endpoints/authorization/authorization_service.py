from fastapi import APIRouter, Header, Depends, Body
from typing import Optional
import logging
from app.config import settings, odoo
from app.utils.erp_db import PostgresDB
from app.utils.redis_client import redis_client as redis_client_instance

import jwt
import datetime
from datetime import timedelta
from app.config import settings
from app.api.deps import get_token_key

REDIS_EXPIRE = 2592000

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
















