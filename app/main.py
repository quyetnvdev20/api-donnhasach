from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import logging

from .config import settings
from .services.rabbitmq import publish_event
from .db_init import init_db
from .api.v1.endpoints import analysis, notifications, masterdata, claim_profile, assessment, assessment_detail, collection_document, repair, repair_masterdata, ocr_quote, odoo_test, report, doc_vision, remote_inspection
from .utils.redis_client import redis_client
from .exceptions.handlers import validation_exception_handler
from .api.v1.endpoints.well_known_file import router as well_known_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    openapi_prefix=settings.API_PREFIX,
    title="Claim AI Service",
    description="Service xử lý các hình ảnh bồi thường của giám định viên",
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
app.include_router(analysis.router, prefix="/claims", tags=["analysis"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(masterdata.router, prefix="/masterdata", tags=["masterdata"])
app.include_router(claim_profile.router, prefix="/profile", tags=["claim_profile"])
app.include_router(assessment.router, prefix="/assessment", tags=["assessments"])
app.include_router(assessment_detail.router, prefix="/assessment", tags=["assessments_detail"])
app.include_router(collection_document.router, prefix="/assessment", tags=["documents"])
app.include_router(report.router, prefix="/assessment", tags=["reports"])
app.include_router(repair.router, prefix="/repairs", tags=["repairs"])
app.include_router(repair_masterdata.router, prefix="/repairs", tags=["repair_masterdata"])
app.include_router(ocr_quote.router, prefix="/repairs", tags=["repairs_ocr"])
app.include_router(odoo_test.router, prefix="/odoo", tags=["odoo"])
app.include_router(doc_vision.router, prefix="/doc-vision", tags=["doc_vision"])
app.include_router(remote_inspection.router, prefix="/remote-inspection", tags=["remote_inspection"])
app.include_router(
    well_known_router,
    prefix="",  # Không thêm prefix vì .well-known cần ở root path
    tags=["well-known"]
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail}
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


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
