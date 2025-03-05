from pydantic_settings import BaseSettings
from enum import Enum

class ClaimImageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class Settings(BaseSettings):
    ROOT_DIR: str = '/'.join(__file__.split('/')[:-2])

    DATABASE_URL: str
    OPENAI_API_KEY: str
    RABBITMQ_URL: str
    KEYCLOAK_HOST: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_CLIENT_SECRET: str

    # Process
    INSURANCE_PROCESSING_API_URL: str
    CLAIM_IMAGE_PROCESS_API_KEY: str
    CLAIM_IMAGE_PROCESS_TIMEOUT: int = 10
    CONCURRENT_WORKERS: int = 10

    # Firebase configuration
    FIREBASE_API_KEY: str = ""
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_FCM_URL: str = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    FIREBASE_TOPIC: str = ""
    
    # Database settings
    POSTGRES_DATABASE_URL: str

    # Odoo configuration
    ODOO_URL: str
    ODOO_TOKEN: str
    
    @property
    def DATABASE_URL(self) -> str:
        return self.POSTGRES_DATABASE_URL
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return self.POSTGRES_DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

    class Config:
        env_file = ".env"

settings = Settings() 