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


def execute_with_optimistic_lock(table: str, record_id: str,
                                  update_query: str, params: tuple,
                                  expected_version: int) -> bool:
    """
    Execute update with optimistic locking.

    Args:
        table: Table name (for logging)
        record_id: Record ID (for logging)
        update_query: UPDATE SQL statement (should include version check)
        params: Query parameters
        expected_version: Expected version number

    Returns:
        True if successful, False if version conflict

    Example:
        success = execute_with_optimistic_lock(
            'instances',
            instance_id,
            "UPDATE instances SET status = %s WHERE id = %s AND version = %s",
            ('running_primary', instance_id, expected_version),
            expected_version
        )
    """
    try:
        # Append version check to WHERE clause if not already present
        if 'AND version = %s' not in update_query.upper():
            # Add version check
            versioned_params = params + (expected_version,)
            versioned_query = update_query + " AND version = %s"
        else:
            versioned_query = update_query
            versioned_params = params

        affected_rows = execute_query(versioned_query, versioned_params, commit=True)

        if affected_rows == 0:
            # Version conflict - record was modified by another transaction
            logger.warning(f"Optimistic lock conflict for {table} id={record_id}, expected_version={expected_version}")
            return False

        logger.debug(f"Optimistic lock success for {table} id={record_id}")
        return True

    except MySQLError as e:
        logger.error(f"Error in optimistic lock update for {table} id={record_id}: {e}")
        return False


def execute_transaction(operations: list) -> bool:
    """
    Execute multiple operations in a single transaction.

    Args:
        operations: List of tuples (query, params)

    Returns:
        True if all operations succeeded, False otherwise
    """
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Execute all operations
        for query, params in operations:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

        # Commit transaction
        conn.commit()

        cursor.close()
        conn.close()

        logger.debug(f"Transaction completed successfully ({len(operations)} operations)")
        return True

    except MySQLError as e:
        logger.error(f"Transaction failed: {e}")

        if conn:
            try:
                conn.rollback()
                logger.info("Transaction rolled back")
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

        return False


def call_stored_procedure(proc_name: str, params: tuple = None) -> Any:
    """
    Call a stored procedure.

    Args:
        proc_name: Procedure name
        params: Tuple of parameters

    Returns:
        Result set from procedure
    """
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if params:
            cursor.callproc(proc_name, params)
        else:
            cursor.callproc(proc_name)

        # Fetch results
        results = []
        for result in cursor.stored_results():
            results.append(result.fetchall())

        conn.commit()

        cursor.close()
        conn.close()

        return results

    except MySQLError as e:
        logger.error(f"Error calling stored procedure {proc_name}: {e}")

        if conn:
            try:
                conn.rollback()
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


# Initialize pool on module load
try:
    initialize_database_pool()
    logger.info("Database layer initialized successfully")
except Exception as e:
    logger.critical(f"CRITICAL: Failed to initialize database: {e}")
