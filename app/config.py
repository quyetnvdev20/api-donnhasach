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
    TOKEN_PREFIX: str

    # Redis configuration
    REDIS_URL: str = ""
    REDIS_DEFAULT_EXPIRY: int = 3600  # 1 hour in seconds

    # Sentry configuration
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    PORTAL_KEY: str

    # Zalo Mini App: secret key để gọi Zalo Open API đổi token (getPhoneNumber) → số điện thoại
    ZALO_APP_SECRET_KEY: str = ""

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

BOOKING_HOURS = [
    {"key": 7, "value": "07:00"},
    {"key": 8, "value": "08:00"},
    {"key": 9, "value": "09:00"},
    {"key": 10, "value": "10:00"},
    {"key": 11, "value": "11:00"},
    {"key": 12, "value": "12:00"},
    {"key": 13, "value": "13:00"},
    {"key": 14, "value": "14:00"},
    {"key": 15, "value": "15:00"},
    {"key": 16, "value": "16:00"},
    {"key": 17, "value": "17:00"},
    {"key": 18, "value": "18:00"},
    {"key": 19, "value": "19:00"},
]

APPOINTMENT_DURATION = [
    {"key": 2, "value": "2 Giờ", "description": "Tối đa 55m2 sàn" },
    {"key": 3, "value": "3 Giờ", "description": "Tối đa 85m2 sàn"},
    {"key": 4, "value": "4 Giờ", "description": "Tối đa 105m2 sàn"},
    {"key": 5, "value": "5 Giờ", "description": "Tối đa 125m2 sàn"},
]

QUANTITY = [
    {"key": 1, "value": "1"},
    {"key": 2, "value": "2"},
    {"key": 3, "value": "3"},
    {"key": 4, "value": "4"},
    {"key": 5, "value": "5"},
    {"key": 6, "value": "6"},
    {"key": 7, "value": "7"},
    {"key": 8, "value": "8"}
]

TIME_OPTIONS = [
    {"key": "days", "value": "Ngày"},
    {"key": "weeks", "value": "Tuần"},
    {"key": "months", "value": "Tháng"},
]

WEEKDAYS = [
    {"key": 0, "label": "Thứ 2"},
    {"key": 1, "label": "Thứ 3"},
    {"key": 2, "label": "Thứ 4"},
    {"key": 3, "label": "Thứ 5"},
    {"key": 4, "label": "Thứ 6"},
    {"key": 5, "label": "Thứ 7"},
    {"key": 6, "label": "Chủ nhật"},
]

EMPLOYEE_QUANTITY = [
    {"key": 1, "value": "1 Nhân viên"},
    {"key": 2, "value": "2 Nhân viên"},
]
