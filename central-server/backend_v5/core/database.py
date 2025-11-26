"""
Database connection pool and query execution utilities.
Provides connection pooling, automatic reconnection, and transaction management.
"""

import mysql.connector
from mysql.connector import pooling, Error as MySQLError
from typing import Any, Optional, Tuple
import logging
from config.settings import (
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD,
    DB_DATABASE, DB_POOL_SIZE, DB_POOL_NAME
)

logger = logging.getLogger(__name__)

# Global connection pool
connection_pool = None


def initialize_database_pool():
    """Initialize MySQL connection pool with error handling."""
    global connection_pool

    try:
        logger.info("Initializing database connection pool...")

        pool_config = {
            'pool_name': DB_POOL_NAME,
            'pool_size': DB_POOL_SIZE,
            'pool_reset_session': True,
            'host': DB_HOST,
            'port': DB_PORT,
            'database': DB_DATABASE,
            'user': DB_USER,
            'password': DB_PASSWORD,
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'autocommit': False,
            'get_warnings': True,
            'raise_on_warnings': False,
        }

        connection_pool = pooling.MySQLConnectionPool(**pool_config)

        # Test the pool
        test_conn = connection_pool.get_connection()
        test_cursor = test_conn.cursor()
        test_cursor.execute("SELECT 1")
        test_cursor.fetchone()
        test_cursor.close()
        test_conn.close()

        logger.info(f"Database connection pool initialized successfully (pool_size={DB_POOL_SIZE})")
        return connection_pool

    except MySQLError as e:
        logger.error(f"Failed to initialize database connection pool: {e}")
        raise


def get_db_connection():
    """Get a database connection from the pool."""
    global connection_pool

    if connection_pool is None:
        initialize_database_pool()

    try:
        conn = connection_pool.get_connection()

        if not conn.is_connected():
            logger.warning("Connection from pool is not alive, reconnecting...")
            conn.reconnect(attempts=3, delay=1)

        return conn

    except MySQLError as e:
        logger.error(f"Error getting database connection: {e}")
        try:
            logger.info("Attempting to reinitialize database pool...")
            initialize_database_pool()
            return connection_pool.get_connection()
        except Exception as retry_error:
            logger.error(f"Failed to reinitialize database pool: {retry_error}")
            raise


def execute_query(query: str, params: tuple = None, fetch_one: bool = False,
                 fetch_all: bool = False, commit: bool = False) -> Any:
    """
    Execute a database query with automatic connection management.

    Args:
        query: SQL query string (use %s for parameters)
        params: Tuple of parameters for parameterized query
        fetch_one: If True, return first row only
        fetch_all: If True, return all rows
        commit: If True, commit the transaction

    Returns:
        - If fetch_one=True: Single row as dictionary or None
        - If fetch_all=True: List of rows as dictionaries
        - If commit=True: Last inserted ID or affected row count
        - Otherwise: Cursor object
    """
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if fetch_one:
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            return result

        elif fetch_all:
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            return result

        elif commit:
            conn.commit()
            last_id = cursor.lastrowid
            affected_rows = cursor.rowcount
            cursor.close()
            conn.close()
            return last_id if last_id else affected_rows

        else:
            return cursor

    except MySQLError as e:
        logger.error(f"Database query error: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")

        if conn and commit:
            try:
                conn.rollback()
                logger.info("Transaction rolled back due to error")
            except:
                pass

        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass

        raise

    except Exception as e:
        logger.error(f"Unexpected error in execute_query: {e}")

        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass

        raise


# Initialize pool on module load
try:
    initialize_database_pool()
    logger.info("Database layer initialized successfully")
except Exception as e:
    logger.critical(f"CRITICAL: Failed to initialize database: {e}")
