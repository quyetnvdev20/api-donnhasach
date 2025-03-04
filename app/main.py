from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .services.rabbitmq import publish_event
from .db_init import init_db
from .api.v1.endpoints import analysis, notifications, assessment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
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

# Include routers
app.include_router(analysis.router, prefix="/claims", tags=["analysis"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(assessment.router, prefix="/assessment", tags=["assessments"])


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
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down")
    # Clean up resources here
