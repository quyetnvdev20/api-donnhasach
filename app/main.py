from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import ValidationError
import logging
import os

from .config import settings
from .services.rabbitmq import publish_event
from .db_init import init_db
from .api.v1.endpoints import ( connect
)
from .utils.redis_client import redis_client
from .exceptions.handlers import validation_exception_handler
from app.utils.sentry import init_sentry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    openapi_prefix=settings.API_PREFIX,
    title="Fast API Tasco Auto",
    description="Fast API Tasco Auto",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)

# Include routers
app.include_router(connect.router, prefix="/connect", tags=["connect"])


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail}
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/test-sentry")
async def test_sentry():
    try:
        # Tạo lỗi cố ý để kiểm tra Sentry
        division_by_zero = 1 / 0
    except Exception as e:
        # Sentry sẽ tự động ghi lại lỗi này nếu được cấu hình đúng
        logger.error(f"Test error for Sentry: {str(e)}")
        raise HTTPException(status_code=500, detail="Test error for Sentry")

@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up")
    try:
        # Initialize database tables
        init_db()
        logger.info("Database initialized successfully")
        
        # Initialize PostgresDB connection pool
        from app.utils.erp_db import PostgresDB
        await PostgresDB.initialize_pool(min_size=10, max_size=50)
        logger.info("PostgreSQL connection pool initialized successfully")
        
        # Initialize Redis connection
        await redis_client.connect()
        logger.info("Redis connection initialized successfully")

        # Khởi tạo Sentry nếu DSN được cung cấp
        if settings.SENTRY_DSN:
            try:
                logger.info(f"Initializing Sentry with DSN: {settings.SENTRY_DSN}")
                init_sentry(
                    dsn=settings.SENTRY_DSN,
                    environment=settings.SENTRY_ENVIRONMENT,
                    traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE
                )
            except Exception as e:
                logger.error(f"Error initializing Sentry: {str(e)}")
        else:
            logger.warning("SENTRY_DSN is not configured, skipping Sentry initialization")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down")
    
    # Close Redis connection
    await redis_client.close()
    logger.info("Redis connection closed")
    
    # Close PostgresDB connection pool
    from app.utils.erp_db import PostgresDB
    await PostgresDB.close_pool()
    logger.info("PostgreSQL connection pool closed")
    
    # Clean up other resources here

def create_app() -> FastAPI:
    # ... existing code ...
    
    # ... existing code ...
    return app
