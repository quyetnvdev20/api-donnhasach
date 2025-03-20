from pydantic_settings import BaseSettings
from enum import Enum
from app.utils.odoo import Odoo

class ClaimImageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class Settings(BaseSettings):
    ROOT_DIR: str = '/'.join(__file__.split('/')[:-2])
    API_PREFIX: str = '/claim-ai'
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
    ODOO_OAUTH_PROVIDER_ID: int = 4
    
    # Report configuration
    ACCIDENT_NOTIFICATION_TEMPLATE: str = ""
    ASSESSMENT_REPORT_TEMPLATE: str = ""
    
    # Insurance API
    INSURANCE_API_URL: str = ""
    
    # Redis configuration
    REDIS_URL: str = ""
    REDIS_DEFAULT_EXPIRY: int = 3600  # 1 hour in seconds
    
    # OCR configuration
    OCR_SERVICE_URL: str = ""
    OCR_API_KEY: str = ""
    OCR_API_SECRET: str = ""

    # Google Maps API
    GOOGLE_MAPS_API_KEY: str = ""

    # Distance limit
    USER_GARAGE_DISTANCE_LIMIT: int = 100
    
    @property
    def DATABASE_URL(self) -> str:
        return self.POSTGRES_DATABASE_URL
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return self.POSTGRES_DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

    class Config:
        env_file = ".env"

settings = Settings()

# Cấu hình Odoo
odoo_config = {
    'ODOO_URL': settings.ODOO_URL,
    'ODOO_TOKEN': settings.ODOO_TOKEN
}

# Khởi tạo đối tượng Odoo
odoo = Odoo(config=odoo_config) 