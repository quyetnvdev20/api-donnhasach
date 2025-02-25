from pydantic_settings import BaseSettings
from enum import Enum

class ClaimImageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class Settings(BaseSettings):
    DATABASE_URL: str
    RABBITMQ_URL: str
    KEYCLOAK_HOST: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_CLIENT_SECRET: str

    # Process
    INSURANCE_PROCESSING_API_URL: str
    CLAIM_IMAGE_PROCESS_API_KEY: str

    # Firebase configuration
    FIREBASE_API_KEY: str = ""
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_FCM_URL: str = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    
    class Config:
        env_file = ".env"

settings = Settings() 