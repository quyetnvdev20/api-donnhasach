from sqlalchemy import create_engine
from app.config import settings
from app.models.base import Base
import logging

logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database by creating all tables."""
    try:
        engine = create_engine(settings.DATABASE_URL)
        Base.metadata.create_all(engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db() 