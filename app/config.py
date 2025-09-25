from pydantic_settings import BaseSettings
from enum import Enum
from app.utils.odoo import Odoo

class Settings(BaseSettings):
    ROOT_DIR: str = '/'.join(__file__.split('/')[:-2])
    API_PREFIX: str = '/api/v1'

    # Firebase configuration
    FIREBASE_API_KEY: str = ""
    FIREBASE_PROJECT_ID: str = ""
    
    # Database settings
    POSTGRES_DATABASE_URL: str

    # Odoo configuration
    ODOO_URL: str
    ODOO_TOKEN: str


    
    # Redis configuration
    REDIS_URL: str = ""
    REDIS_DEFAULT_EXPIRY: int = 3600  # 1 hour in seconds

    # Sentry configuration
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

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