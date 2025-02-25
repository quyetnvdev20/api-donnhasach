import requests
import json
import logging
import socket
import time
from ..config import settings
from typing import List, Dict, Any, Optional
import google.auth.transport.requests
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

class FirebaseNotificationService:
    """Service for sending notifications via Firebase Cloud Messaging (FCM)"""
    
    # Lưu trữ token và thời gian hết hạn để tái sử dụng
    _access_token = None
    _token_expiry = 0
    
    @staticmethod
    def _get_access_token():
        """Lấy token OAuth 2.0 từ tài khoản dịch vụ Firebase"""
        current_time = time.time()
        
        # Kiểm tra xem token hiện tại còn hiệu lực không
        if (FirebaseNotificationService._access_token is None or 
            current_time >= FirebaseNotificationService._token_expiry):
            
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    'app/utils/firebase-service-account.json',
                    scopes=['https://www.googleapis.com/auth/firebase.messaging']
                )
                
                request = google.auth.transport.requests.Request()
                credentials.refresh(request)
                
                FirebaseNotificationService._access_token = credentials.token
                # Token OAuth thường có hiệu lực trong 1 giờ
                FirebaseNotificationService._token_expiry = current_time + 3500  # 3500s = 58 phút
                
                logger.info("Đã tạo mới token xác thực OAuth 2.0 cho Firebase")
            except Exception as e:
                logger.error(f"Lỗi khi lấy token OAuth 2.0: {str(e)}")
                logger.exception("Chi tiết lỗi:")
                return None
            
        return FirebaseNotificationService._access_token

    @staticmethod
    async def send_notification_to_device(
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        platform: Optional[str] = None,  # 'ios' or 'android'
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Send a notification to a specific device using FCM v1 API
        """
        if not device_token:
            logger.warning("Không có token thiết bị, bỏ qua thông báo")
            return {"success": False, "error": "Không có token thiết bị"}

        # Lấy OAuth token
        access_token = FirebaseNotificationService._get_access_token()
        if not access_token:
            logger.error("Không thể lấy token OAuth 2.0")
            return {"success": False, "error": "Lỗi xác thực"}

        # Format the FCM URL with the project ID
        fcm_url = settings.FIREBASE_FCM_URL.format(project_id=settings.FIREBASE_PROJECT_ID)
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }

        # Chuẩn bị thông báo
        notification = {
            "title": title,
            "body": body
        }

        # Chuẩn bị message
        message = {
            "message": {
                "token": device_token,
                "notification": notification
            }
        }

        # Cấu hình cho từng nền tảng
        if platform == "ios":
            message["message"]["apns"] = {
                "payload": {
                    "aps": {
                        "sound": "default",
                        "badge": 1,
                        "content-available": 1,
                        "mutable-content": 1
                    }
                }
            }
        elif platform == "android":
            message["message"]["android"] = {
                "priority": "high",
                "notification": {
                    "sound": "default",
                    "notification_priority": "PRIORITY_HIGH",
                    "default_sound": True,
                    "default_vibrate_timings": True,
                    "default_light_settings": True
                }
            }

        # Thêm data nếu có
        if data:
            message["message"]["data"] = data

        if debug:
            logger.debug(f"Gửi thông báo đến thiết bị {device_token}")
            logger.debug(f"URL: {fcm_url}")
            logger.debug(f"Payload: {json.dumps(message, indent=2)}")

        try:
            response = requests.post(
                fcm_url, 
                headers=headers, 
                json=message,
                timeout=10.0
            )
            
            try:
                response_data = response.json()
            except ValueError:
                response_data = {"error": "Phản hồi không hợp lệ từ Firebase"}
                logger.error(f"Không thể phân tích phản hồi JSON: {response.text}")

            if response.status_code in (200, 201):
                logger.info(f"Thông báo đã gửi thành công đến thiết bị {device_token}")
                return {"success": True, "response": response_data}
            else:
                logger.error(f"Lỗi khi gửi thông báo: {response_data}")
                return {"success": False, "error": response_data}

        except requests.exceptions.Timeout:
            error_msg = "Hết thời gian chờ khi gửi thông báo"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            logger.error(f"Lỗi khi gửi thông báo: {str(e)}")
            logger.exception("Chi tiết lỗi:")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def send_notification_to_topic(
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Send a data-only (silent) message to a topic using FCM v1 API
        
        Args:
            topic: The FCM topic to send to
            title: Will be included in data payload
            body: Will be included in data payload
            data: Additional data payload to send
            debug: Enable detailed debug logging
        """
        # Lấy OAuth token
        access_token = FirebaseNotificationService._get_access_token()
        if not access_token:
            logger.error("Không thể lấy token OAuth 2.0")
            return {"success": False, "error": "Lỗi xác thực"}

        # Format the FCM URL with the project ID
        fcm_url = settings.FIREBASE_FCM_URL.format(project_id=settings.FIREBASE_PROJECT_ID)
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }

        # Kết hợp tất cả dữ liệu vào data payload
        message_data = {
            "title": title,
            "body": body,
            **(data or {})
        }

        # Chuẩn bị message (data-only)
        message = {
            "message": {
                "topic": topic,
                "data": message_data,
                # Cấu hình cho Android
                "android": {
                    "priority": "high",
                    "ttl": "86400s",  # 24 hours
                    "direct_boot_ok": True
                },
                # Cấu hình cho iOS
                "apns": {
                    "headers": {
                        "apns-priority": "5",
                        "apns-push-type": "background"
                    },
                    "payload": {
                        "aps": {
                            "content-available": 1,
                            "sound": "",  # Empty sound for silent notification
                            "badge": 0
                        }
                    }
                }
            }
        }

        if debug:
            logger.debug(f"Gửi data message đến topic {topic}")
            logger.debug(f"URL: {fcm_url}")
            logger.debug(f"Payload: {json.dumps(message, indent=2)}")

        try:
            response = requests.post(
                fcm_url, 
                headers=headers, 
                json=message,
                timeout=10.0
            )
            
            try:
                response_data = response.json()
            except ValueError:
                response_data = {"error": "Phản hồi không hợp lệ từ Firebase"}
                logger.error(f"Không thể phân tích phản hồi JSON: {response.text}")

            if response.status_code in (200, 201):
                logger.info(f"Data message đã gửi thành công đến topic {topic}")
                return {"success": True, "response": response_data}
            else:
                logger.error(f"Lỗi khi gửi data message đến topic: {response_data}")
                return {"success": False, "error": response_data}

        except requests.exceptions.Timeout:
            error_msg = "Hết thời gian chờ khi gửi data message"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            logger.error(f"Lỗi khi gửi data message đến topic: {str(e)}")
            logger.exception("Chi tiết lỗi:")
            return {"success": False, "error": str(e)} 