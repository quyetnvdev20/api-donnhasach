from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from pydantic import ValidationError
import logging
from .api.v1.endpoints.blog import router as blog_router
from .api.v1.endpoints.authorization import router as authorization_router
from .api.v1.endpoints.category import router as category_router
from .api.v1.endpoints.partner import router as partner_router
from .config import settings
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
app.include_router(blog_router, prefix="/blog", tags=["blog"])
app.include_router(authorization_router, prefix="/authorization", tags=["authorization"])
app.include_router(category_router, prefix="/category", tags=["category"])
app.include_router(partner_router, prefix="/partner", tags=["partner"])

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail}
    )

@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up")
    try:
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
