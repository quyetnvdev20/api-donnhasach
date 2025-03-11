import logging
from typing import Any, Dict
import psycopg2
from psycopg2.extras import RealDictCursor
import asyncpg
from ..config import settings

logger = logging.getLogger(__name__)

class PostgresDB:
    _pool = None


    @classmethod
    async def initialize_pool(cls, min_size=5, max_size=10):
        """Initialize a connection pool once during application startup"""
        if cls._pool is None:
            try:
                cls._pool = await asyncpg.create_pool(
                    settings.POSTGRES_DATABASE_URL,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=60,
                    max_inactive_connection_lifetime=300
                )
                logger.info("PostgreSQL connection pool initialized")
            except Exception as e:
                logger.error(f"Error initializing PostgreSQL connection pool: {str(e)}")
                raise
        return cls._pool

    @classmethod
    async def close_pool(cls):
        """Close the connection pool during application shutdown"""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("PostgreSQL connection pool closed")

    @classmethod
    async def get_pool(cls):
        """Get the connection pool, initializing if necessary"""
        if cls._pool is None:
            await cls.initialize_pool()
        return cls._pool

    @classmethod
    async def execute_query(cls, query: str, params: Any = None) -> list:
        """Execute a query and return results"""
        pool = await cls.get_pool()
        try:
            async with pool.acquire() as connection:
                if params is None:
                    results = await connection.fetch(query)
                elif isinstance(params, dict):
                    # Convert named parameters from %(name)s to positional $1, $2, etc.
                    param_names = list(params.keys())
                    param_values = [params[name] for name in param_names]
                    
                    # Replace %(name)s with $1, $2, etc.
                    for i, name in enumerate(param_names, 1):
                        query = query.replace(f"%({name})s", f"${i}")
                    
                    # Execute with positional parameters
                    results = await connection.fetch(query, *param_values)
                else:
                    # Handle list parameters
                    results = await connection.fetch(query, *params)
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            raise

    @classmethod
    async def execute_transaction(cls, queries: list) -> None:
        """Execute multiple queries in a transaction"""
        pool = await cls.get_pool()
        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    for query in queries:
                        await connection.execute(query)
        except Exception as e:
            logger.error(f"Error executing transaction: {str(e)}")
            raise

# Khởi tạo pool khi ứng dụng khởi động
async def startup_event():
    await PostgresDB.initialize_pool(min_size=10, max_size=50)

# Đóng pool khi ứng dụng shutdown
async def shutdown_event():
    await PostgresDB.close_pool()

# # Sử dụng trong các endpoint
# async def handle_request():
#     data = await PostgresDB.execute_query("SELECT * FROM table WHERE id = $1", [1])
#     return data 