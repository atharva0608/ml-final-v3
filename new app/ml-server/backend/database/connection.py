"""
Database Connection Pool Management
Uses asyncpg for PostgreSQL async connections
"""

import asyncpg
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global connection pool
db_pool: Optional[asyncpg.Pool] = None


async def init_db(
    host: str = "localhost",
    port: int = 5432,
    database: str = "ml_server",
    user: str = "ml_server",
    password: str = "ml_server_password",
    min_size: int = 10,
    max_size: int = 20
) -> asyncpg.Pool:
    """
    Initialize database connection pool

    Args:
        host: Database host
        port: Database port
        database: Database name
        user: Database user
        password: Database password
        min_size: Minimum pool size
        max_size: Maximum pool size

    Returns:
        asyncpg.Pool: Connection pool
    """
    global db_pool

    logger.info(f"Initializing database connection pool...")
    logger.info(f"Host: {host}:{port}, Database: {database}")

    db_pool = await asyncpg.create_pool(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        min_size=min_size,
        max_size=max_size,
        command_timeout=60
    )

    logger.info(f"✓ Database pool created (min={min_size}, max={max_size})")
    return db_pool


async def get_db() -> asyncpg.Pool:
    """
    Get database connection pool

    Returns:
        asyncpg.Pool: Active connection pool

    Raises:
        RuntimeError: If pool not initialized
    """
    if db_pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return db_pool


async def close_db():
    """Close database connection pool"""
    global db_pool

    if db_pool is not None:
        logger.info("Closing database connection pool...")
        await db_pool.close()
        db_pool = None
        logger.info("✓ Database pool closed")
