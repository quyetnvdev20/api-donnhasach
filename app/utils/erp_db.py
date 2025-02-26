import logging
from typing import Any, Dict
import psycopg2
from psycopg2.extras import RealDictCursor
import asyncpg
from ..config import settings

logger = logging.getLogger(__name__)

class PostgresDB:
    @staticmethod
    async def get_async_connection():
        """Get async connection pool for PostgreSQL"""
        try:
            pool = await asyncpg.create_pool(settings.POSTGRES_DATABASE_URL)
            return pool
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {str(e)}")
            raise

    @staticmethod
    def get_sync_connection():
        """Get synchronous connection for PostgreSQL"""
        try:
            return psycopg2.connect(
                settings.POSTGRES_DATABASE_URL,
                cursor_factory=RealDictCursor
            )
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {str(e)}")
            raise

    @staticmethod
    async def execute_query(query: str, params: list = None) -> list:
        """Execute a query and return results"""
        pool = await PostgresDB.get_async_connection()
        try:
            async with pool.acquire() as connection:
                if params:
                    results = await connection.fetch(query, *params)
                else:
                    results = await connection.fetch(query)
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            raise
        finally:
            await pool.close()

    @staticmethod
    async def execute_transaction(queries: list) -> None:
        """Execute multiple queries in a transaction"""
        pool = await PostgresDB.get_async_connection()
        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    for query in queries:
                        await connection.execute(query)
        except Exception as e:
            logger.error(f"Error executing transaction: {str(e)}")
            raise
        finally:
            await pool.close() 