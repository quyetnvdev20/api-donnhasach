from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .services.rabbitmq import publish_event
from .workers.image_processor import process_message
from .db_init import init_db
from .api.v1.endpoints import plate_analysis

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
app.include_router(plate_analysis.router, prefix="/api/v1", tags=["plate-analysis"])

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

# Example endpoint to demonstrate RabbitMQ integration
@app.post("/api/v1/test-worker")
async def test_worker():
    try:
        # Example of publishing a message to RabbitMQ
        await publish_event("test.event", {"message": "This is a test message"})
        return {"status": "Message sent to worker"}
    except Exception as e:
        logger.error(f"Error sending message to worker: {str(e)}")
        return {"status": "error", "message": str(e)} 
