import requests
import json
import logging
from ..config import settings
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class FirebaseNotificationService:
    """Service for sending notifications via Firebase Cloud Messaging (FCM)"""
    
    @staticmethod
    async def send_notification_to_device(
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        platform: Optional[str] = None  # 'ios' or 'android'
    ) -> Dict[str, Any]:
        """
        Send a notification to a specific device using FCM
        
        Args:
            device_token: The FCM registration token of the target device
            title: Notification title
            body: Notification body text
            data: Optional data payload to send with the notification
            platform: Optional platform identifier ('ios' or 'android')
            
        Returns:
            Response from Firebase API
        """
        if not device_token:
            logger.warning("No device token provided, skipping notification")
            return {"success": False, "error": "No device token provided"}
            
        # Format the FCM URL with the project ID
        fcm_url = settings.FIREBASE_FCM_URL.format(project_id=settings.FIREBASE_PROJECT_ID)
        
        # Set up the authorization header
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.FIREBASE_API_KEY}'
        }
        
        # Prepare the message payload
        message = {
            "message": {
                "token": device_token,
                "notification": {
                    "title": title,
                    "body": body
                }
            }
        }
        
        # Add platform-specific configurations
        if platform == "ios":
            message["message"]["apns"] = {
                "payload": {
                    "aps": {
                        "sound": "default",
                        "badge": 1,
                        # iOS specific configurations
                    }
                }
            }
        elif platform == "android":
            message["message"]["android"] = {
                "priority": "high",
                # Android specific configurations
            }
        
        # Add data payload if provided
        if data:
            message["message"]["data"] = data
        
        try:
            # Send the request to Firebase
            response = requests.post(fcm_url, headers=headers, data=json.dumps(message))
            response_data = response.json()
            
            if response.status_code == 200:
                logger.info(f"Notification sent successfully to device {device_token}")
                return {"success": True, "response": response_data}
            else:
                logger.error(f"Failed to send notification: {response_data}")
                return {"success": False, "error": response_data}
                
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def send_notification_to_topic(
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Send a notification to a topic using FCM
        
        Args:
            topic: The FCM topic to send to
            title: Notification title
            body: Notification body text
            data: Optional data payload to send with the notification
            
        Returns:
            Response from Firebase API
        """
        # Format the FCM URL with the project ID
        fcm_url = settings.FIREBASE_FCM_URL.format(project_id=settings.FIREBASE_PROJECT_ID)
        
        # Set up the authorization header
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.FIREBASE_API_KEY}'
        }
        
        # Prepare the message payload
        message = {
            "message": {
                "topic": topic,
                "notification": {
                    "title": title,
                    "body": body
                }
            }
        }
        
        # Add data payload if provided
        if data:
            message["message"]["data"] = data
        
        try:
            # Send the request to Firebase
            response = requests.post(fcm_url, headers=headers, data=json.dumps(message))
            response_data = response.json()
            
            if response.status_code == 200:
                logger.info(f"Notification sent successfully to topic {topic}")
                return {"success": True, "response": response_data}
            else:
                logger.error(f"Failed to send notification to topic: {response_data}")
                return {"success": False, "error": response_data}
                
        except Exception as e:
            logger.error(f"Error sending notification to topic: {str(e)}")
            return {"success": False, "error": str(e)} 