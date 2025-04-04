import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from app.config import settings
import logging

logger = logging.getLogger(__name__)

def init_sentry(dsn, environment, traces_sample_rate=0.1):
    """
    Khởi tạo Sentry với các cấu hình cần thiết
    
    Args:
        dsn: Sentry DSN
        environment: Môi trường (development, staging, production)
        traces_sample_rate: Tỷ lệ lấy mẫu cho performance monitoring
    """
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration(),
            HttpxIntegration(),
            StarletteIntegration()
        ],
        
        # Cấu hình thêm
        send_default_pii=True,  # Gửi thông tin nhận dạng cá nhân
        attach_stacktrace=True,  # Đính kèm stack trace cho các sự kiện
        max_breadcrumbs=50,      # Số lượng breadcrumbs tối đa
        
        # Bỏ qua một số lỗi không cần thiết
        ignore_errors=[
            "HTTPException",     # Bỏ qua các lỗi HTTP thông thường
        ],
    )
    
    logger.info(f"Sentry đã được khởi tạo với môi trường: {environment}") 