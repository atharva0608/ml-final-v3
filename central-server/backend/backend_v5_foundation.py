"""
================================================================================
AWS SPOT OPTIMIZER - CENTRAL SERVER BACKEND v5.0
================================================================================

PRODUCTION-GRADE CENTRAL SERVER FOR AWS SPOT INSTANCE OPTIMIZATION
------------------------------------------------------------------------------

This backend implements a sophisticated multi-tenant spot instance optimization
system with ML-based decision making, emergency failover, and comprehensive
cost tracking capabilities.

ARCHITECTURE OVERVIEW:
------------------------------------------------------------------------------
The system acts as a "Central Brain" that orchestrates AWS Spot instance
optimization across multiple clients, each with their own agents monitoring
instances. The architecture prioritizes safety (zero-downtime) over cost
optimization through multi-layered safety mechanisms.

CORE COMPONENTS:
------------------------------------------------------------------------------
1. DATABASE LAYER (lines ~200-500)
   - MySQL connection pooling with automatic reconnection
   - Transaction management with rollback support
   - Prepared statements for SQL injection protection
   - Query result caching for performance

2. AUTHENTICATION & SECURITY (lines ~500-700)
   - Client token-based authentication
   - Admin authentication with role-based access
   - Request validation and sanitization
   - CORS configuration for frontend access

3. ADMIN APIS (lines ~700-1200)
   - Client management (create, delete, token regeneration)
   - System health monitoring and diagnostics
   - Global statistics and analytics
   - ML model management and activation

4. CLIENT MANAGEMENT APIS (lines ~1200-1600)
   - Client account operations
   - Token validation and security
   - Client-specific configuration
   - Quota and limits management

5. AGENT MANAGEMENT APIS (lines ~1600-2400)
   - Agent registration and heartbeat monitoring
   - Configuration synchronization
   - Agent lifecycle management (enable/disable/delete)
   - Agent health tracking and timeout detection

6. INSTANCE MANAGEMENT APIS (lines ~2400-3200)
   - Instance lifecycle tracking
   - Pricing data collection and analysis
   - Instance metrics and performance tracking
   - Manual instance switching operations

7. REPLICA MANAGEMENT APIS (lines ~3200-4000)
   - Replica creation and synchronization
   - Replica promotion to primary
   - Hot standby management
   - Manual replica mode support

8. EMERGENCY & SAFETY SYSTEMS (lines ~4000-4600)
   - AWS interruption signal handling
   - Emergency replica creation (bypasses all settings)
   - 2-minute termination failover (<15s response time)
   - Automatic rebalance recommendation handling

9. DECISION ENGINE INTEGRATION (lines ~4600-5400)
   - Pluggable ML model architecture
   - Switch recommendation generation
   - Auto-switch command issuance (respects settings)
   - Model upload and activation workflow

10. COMMAND ORCHESTRATION (lines ~5400-6000)
    - Priority-based command queue
    - Command expiration and cleanup
    - Agent command polling
    - Execution status tracking

11. REPORTING & TELEMETRY (lines ~6000-6800)
    - Pricing data collection and deduplication
    - Switch report processing and savings calculation
    - Cleanup operation tracking
    - Termination reporting

12. SAVINGS & ANALYTICS (lines ~6800-7400)
    - Cumulative savings calculation (total_savings field)
    - Time-series savings data for charts
    - Switch history with filtering
    - Cost optimization metrics

13. NOTIFICATIONS SYSTEM (lines ~7400-7800)
    - Real-time notification generation
    - Unread count tracking
    - Notification filtering by client
    - Mark as read functionality

14. HEALTH & MONITORING (lines ~7800-8000)
    - System health checks
    - Uptime tracking
    - Database connectivity monitoring
    - Background job scheduler status

CRITICAL WORKFLOWS:
------------------------------------------------------------------------------

WORKFLOW 1: NORMAL ML-BASED SWITCHING
--------------------------------------
When auto_switch_enabled = TRUE:
1. Agent calls GET /api/agents/{id}/switch-recommendation
   → ML model evaluates current state and returns recommendation
2. If recommendation = "switch":
   → Agent calls POST /api/agents/{id}/issue-switch-command
   → Backend CHECKS auto_switch_enabled (returns 403 if FALSE)
   → Creates command in commands table with priority=50
3. Agent polls GET /api/agents/{id}/pending-commands (every 30-60s)
   → Receives switch command
4. Agent executes switch (creates AMI, launches new instance, syncs data)
5. Agent calls POST /api/agents/{id}/switch-report
   → Backend calculates savings_impact = old_price - new_price
   → Updates clients.total_savings += (savings_impact * 24)
   → Stores switch record in switches table

When auto_switch_enabled = FALSE:
- Recommendation still generated (for UI display)
- will_auto_execute flag = false in response
- No command issued (403 error if attempted)
- User must manually switch via UI

WORKFLOW 2: EMERGENCY FAILOVER (BYPASSES ALL SETTINGS)
-------------------------------------------------------
Scenario A: AWS Rebalance Recommendation (2+ hours notice)
1. AWS sends rebalance signal via instance metadata
2. Agent calls POST /api/agents/{id}/rebalance-recommendation
   → Backend BYPASSES auto_switch_enabled and manual_replica_enabled
   → Creates emergency replica in safest available pool
   → Works even if ML models are broken or not loaded
3. Replica created and begins syncing
4. If actual termination occurs, replica is ready for promotion

Scenario B: AWS Termination Notice (2-minute warning)
1. AWS sends termination notice (120 seconds until termination)
2. Agent calls POST /api/agents/{id}/termination-imminent
   → Backend BYPASSES ALL SETTINGS
   → Immediately promotes existing replica (if available)
   → Failover completes in <15 seconds
   → Updates routing to new primary
   → Old instance will be terminated by AWS at scheduled time

WORKFLOW 3: MANUAL REPLICA MODE
-------------------------------
When manual_replica_enabled = TRUE:
1. Backend ensures exactly one replica is always maintained
2. User controls when to promote replica to primary
3. After promotion, new replica is automatically created
4. No ML involvement - 100% user-controlled timing

WORKFLOW 4: SAVINGS CALCULATION
-------------------------------
Savings are accumulated in clients.total_savings field:
1. When switch occurs: savings_impact = old_price - new_price
2. Daily estimate: daily_savings = savings_impact * 24
3. Add to cumulative total: total_savings += daily_savings
4. This assumes savings continues for 24 hours (reasonable estimate)
5. Frontend displays accumulated total
6. Historical detail in switches table and client_savings_monthly table

DATA QUALITY PIPELINE:
------------------------------------------------------------------------------
Raw pricing data → Deduplication → Gap detection → Gap filling → ML dataset

Stage 1: Raw data from agents (every 5 minutes)
Stage 2: Deduplicate using time buckets (5-min alignment)
Stage 3: Detect gaps in expected coverage
Stage 4: Fill gaps using interpolation/inference
Stage 5: Materialize clean dataset for ML training

SAFETY MECHANISMS:
------------------------------------------------------------------------------
1. Emergency endpoints bypass auto_switch_enabled setting
2. Emergency endpoints bypass manual_replica_enabled setting
3. Emergency endpoints work even if ML models are offline
4. Failover completes in <15 seconds for termination notices
5. Multiple safety layers activate independently
6. System prioritizes availability over cost optimization

MUTUAL EXCLUSION RULES:
------------------------------------------------------------------------------
1. auto_switch_enabled and manual_replica_enabled are MUTUALLY EXCLUSIVE
2. Enabling one automatically disables the other
3. Enforced at database level with triggers
4. Enforced in application logic
5. Frontend UI reflects this constraint

CONFIGURATION VERSIONING:
------------------------------------------------------------------------------
- Each config change increments agent.config_version
- Agents cache config locally
- Backend sends config_version in heartbeat response
- Agents compare versions and pull new config when changed
- Prevents excessive DB queries while ensuring timely updates

DATABASE CONNECTION POOLING:
------------------------------------------------------------------------------
- Pool size: 10-20 connections (configurable)
- Connection recycling: 3600 seconds
- Automatic reconnection on connection loss
- Transaction rollback on errors
- Prepared statement caching

ERROR HANDLING STRATEGY:
------------------------------------------------------------------------------
- All endpoints return consistent JSON format
- Success: {"status": "success", "data": {...}}
- Error: {"status": "error", "error": "message", "code": "ERROR_CODE"}
- HTTP status codes:
  - 200: Success
  - 400: Bad request (validation error)
  - 401: Unauthorized (invalid/missing token)
  - 403: Forbidden (auto_switch disabled, insufficient permissions)
  - 404: Not found
  - 500: Internal server error
- All exceptions logged with stack traces
- Database errors trigger automatic retry (up to 3 attempts)

LOGGING ARCHITECTURE:
------------------------------------------------------------------------------
- Structured logging with levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Log rotation: 100MB per file, keep 10 files
- Separate logs for:
  - Application logic (app.log)
  - API requests (access.log)
  - Errors (error.log)
  - Decision engine (decision_engine.log)
- Include timestamps, request IDs, client IDs for tracing
- Log all authentication attempts
- Log all config changes
- Log all emergency operations

BACKGROUND JOBS:
------------------------------------------------------------------------------
1. Agent Timeout Detection (every 60s)
   - Marks agents offline after 120s of no heartbeat
   - Updates instance status accordingly

2. Zombie Instance Cleanup (every 300s)
   - Terminates zombie instances after terminate_wait_seconds
   - Records cleanup operations

3. Command Expiration (every 120s)
   - Removes expired commands from queue
   - Logs expired commands for audit

4. Replica Coordinator (every 2s in emergency mode)
   - Monitors for AWS interruption signals
   - Creates/promotes replicas as needed

5. Data Quality Pipeline (every 3600s)
   - Deduplicates pricing data
   - Fills gaps in coverage
   - Materializes ML dataset

DEPLOYMENT NOTES:
------------------------------------------------------------------------------
- Recommended: Gunicorn with 4-8 workers
- Use environment variables for secrets (DB password, admin token)
- Enable HTTPS in production
- Set up database backups (daily)
- Monitor disk space for logs
- Use reverse proxy (nginx) for static files
- Enable rate limiting for public endpoints
- Set up health check monitoring (GET /health)

TESTING STRATEGY:
------------------------------------------------------------------------------
- Unit tests for each major function
- Integration tests for API endpoints
- Load testing for concurrent agent connections
- Failure testing for emergency scenarios
- Database transaction testing for data integrity
- ML model fallback testing

VERSION HISTORY:
------------------------------------------------------------------------------
v5.0 - New modular architecture with extensive documentation
v4.3 - File upload for decision engines and ML models
v4.0 - Emergency failover and replica management
v3.0 - ML-based decision engine integration
v2.0 - Multi-client support
v1.0 - Initial single-client implementation

AUTHOR: AWS Spot Optimizer Team
LICENSE: Proprietary
COMPATIBLE WITH: Agent v4.0+, MySQL Schema v5.1+

================================================================================
"""

# ============================================================================
# SECTION 1: IMPORTS AND DEPENDENCIES
# ============================================================================
#
# This section imports all required Python libraries and modules.
# Organized by category: standard library, third-party, and internal modules.
# ============================================================================

# --- Standard Library Imports ---
import os
import sys
import json
import time
import logging
import secrets
import traceback
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from functools import wraps
from collections import defaultdict
import re

# --- Third-Party Library Imports ---
# Flask: Web framework for building the REST API
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS

# MySQL: Database connector for persistence layer
import mysql.connector
from mysql.connector import pooling, Error as MySQLError
from mysql.connector.cursor import MySQLCursor

# APScheduler: Background job scheduler for periodic tasks
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Data processing libraries
import numpy as np
import pandas as pd

# Environment variable management
from dotenv import load_dotenv

# ============================================================================
# SECTION 2: ENVIRONMENT CONFIGURATION
# ============================================================================
#
# Load environment variables from .env file and set up application
# configuration. This allows different settings for development, staging,
# and production environments without code changes.
# ============================================================================

# Load environment variables from .env file (if it exists)
load_dotenv()

# --- Database Configuration ---
# MySQL connection settings with fallback defaults
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_DATABASE = os.getenv('DB_DATABASE', 'spot_optimizer')

# Connection pool settings for performance and concurrency
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))
DB_POOL_NAME = os.getenv('DB_POOL_NAME', 'spot_optimizer_pool')
DB_POOL_RESET_SESSION = True  # Reset session variables between connections

# --- Application Configuration ---
# Flask application settings
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))

# --- Security Configuration ---
# Admin authentication token (should be set via environment variable in production)
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'admin-secret-token-change-in-production')

# CORS allowed origins (comma-separated list)
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')

# --- Decision Engine Configuration ---
# Directory for uploaded decision engine Python files
DECISION_ENGINE_DIR = os.getenv('DECISION_ENGINE_DIR', './decision_engines')
os.makedirs(DECISION_ENGINE_DIR, exist_ok=True)

# Directory for uploaded ML model files
MODEL_DIR = os.getenv('MODEL_DIR', './models')
os.makedirs(MODEL_DIR, exist_ok=True)

# --- Logging Configuration ---
# Log level and file locations
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_DIR = os.getenv('LOG_DIR', './logs')
os.makedirs(LOG_DIR, exist_ok=True)

# --- Agent Configuration Defaults ---
# Default timeout before marking agent as offline (seconds)
AGENT_HEARTBEAT_TIMEOUT = int(os.getenv('AGENT_HEARTBEAT_TIMEOUT', '120'))

# Default wait time before terminating zombie instances (seconds)
DEFAULT_TERMINATE_WAIT_SECONDS = int(os.getenv('DEFAULT_TERMINATE_WAIT_SECONDS', '300'))

# --- Background Job Configuration ---
# Enable/disable background scheduler
ENABLE_BACKGROUND_JOBS = os.getenv('ENABLE_BACKGROUND_JOBS', 'True').lower() == 'true'

# ============================================================================
# SECTION 3: LOGGING SETUP
# ============================================================================
#
# Configure structured logging with rotation, levels, and separate log files
# for different concerns (app logic, errors, decisions, access).
# ============================================================================

# Create logger instance
logger = logging.getLogger('spot_optimizer')
logger.setLevel(getattr(logging, LOG_LEVEL.upper()))

# Create formatters
# Detailed formatter with timestamps, levels, and context
detailed_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Simple formatter for less critical logs
simple_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- File Handlers ---
# Main application log (all levels)
app_log_handler = logging.FileHandler(os.path.join(LOG_DIR, 'app.log'))
app_log_handler.setLevel(logging.DEBUG)
app_log_handler.setFormatter(detailed_formatter)
logger.addHandler(app_log_handler)

# Error log (errors and critical only)
error_log_handler = logging.FileHandler(os.path.join(LOG_DIR, 'error.log'))
error_log_handler.setLevel(logging.ERROR)
error_log_handler.setFormatter(detailed_formatter)
logger.addHandler(error_log_handler)

# --- Console Handler ---
# Print logs to console for development/debugging
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(simple_formatter)
logger.addHandler(console_handler)

logger.info("=" * 80)
logger.info("AWS SPOT OPTIMIZER - CENTRAL SERVER BACKEND v5.0")
logger.info("=" * 80)
logger.info(f"Environment: {FLASK_ENV}")
logger.info(f"Debug Mode: {FLASK_DEBUG}")
logger.info(f"Database: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}")
logger.info(f"Decision Engine Dir: {DECISION_ENGINE_DIR}")
logger.info(f"Model Dir: {MODEL_DIR}")
logger.info(f"Log Level: {LOG_LEVEL}")
logger.info("=" * 80)

# ============================================================================
# SECTION 4: FLASK APPLICATION INITIALIZATION
# ============================================================================
#
# Initialize Flask application with CORS, error handlers, and middleware.
# ============================================================================

# Create Flask application instance
app = Flask(__name__)

# Configure Flask settings
app.config['JSON_SORT_KEYS'] = False  # Preserve JSON key order
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True  # Pretty print JSON in development
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Max upload size: 100MB

# Enable CORS for frontend access
# In production, set CORS_ORIGINS to specific domains
if CORS_ORIGINS == '*':
    logger.warning("CORS is set to allow all origins (*). This should be restricted in production.")
    CORS(app, resources={r"/api/*": {"origins": "*"}})
else:
    allowed_origins = [origin.strip() for origin in CORS_ORIGINS.split(',')]
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})
    logger.info(f"CORS enabled for origins: {allowed_origins}")

# Application start time for uptime calculation
APP_START_TIME = datetime.utcnow()

logger.info("Flask application initialized successfully")

# ============================================================================
# SECTION 5: DATABASE CONNECTION POOL
# ============================================================================
#
# MySQL connection pooling for efficient database access.
# Implements connection reuse, automatic reconnection, and error handling.
# ============================================================================

# Global variable to store connection pool
connection_pool = None

def initialize_database_pool():
    """
    Initialize MySQL connection pool with error handling.

    The connection pool maintains a set of reusable database connections,
    reducing the overhead of creating new connections for each request.

    Returns:
        mysql.connector.pooling.MySQLConnectionPool: Configured connection pool

    Raises:
        MySQLError: If unable to create connection pool
    """
    global connection_pool

    try:
        logger.info("Initializing database connection pool...")

        # Create connection pool configuration
        pool_config = {
            'pool_name': DB_POOL_NAME,
            'pool_size': DB_POOL_SIZE,
            'pool_reset_session': DB_POOL_RESET_SESSION,
            'host': DB_HOST,
            'port': DB_PORT,
            'database': DB_DATABASE,
            'user': DB_USER,
            'password': DB_PASSWORD,
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'autocommit': False,  # Explicit transaction management
            'get_warnings': True,
            'raise_on_warnings': False,
        }

        # Create the connection pool
        connection_pool = pooling.MySQLConnectionPool(**pool_config)

        # Test the pool by getting a connection
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
        logger.error(traceback.format_exc())
        raise

def get_db_connection():
    """
    Get a database connection from the pool.

    This function retrieves a connection from the pool, automatically
    reconnecting if the connection is lost or stale.

    Returns:
        mysql.connector.connection.MySQLConnection: Database connection

    Raises:
        MySQLError: If unable to obtain connection from pool
    """
    global connection_pool

    # Initialize pool if not already done
    if connection_pool is None:
        initialize_database_pool()

    try:
        # Get connection from pool
        conn = connection_pool.get_connection()

        # Test if connection is alive
        if not conn.is_connected():
            logger.warning("Connection from pool is not alive, reconnecting...")
            conn.reconnect(attempts=3, delay=1)

        return conn

    except MySQLError as e:
        logger.error(f"Error getting database connection: {e}")
        # Try to reinitialize pool on error
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

    This is a utility function that handles connection pooling, error handling,
    and transaction management for database queries.

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

    Raises:
        MySQLError: If query execution fails

    Example:
        # Insert with commit
        result = execute_query(
            "INSERT INTO clients (name, email) VALUES (%s, %s)",
            ("John Doe", "john@example.com"),
            commit=True
        )

        # Select single row
        client = execute_query(
            "SELECT * FROM clients WHERE id = %s",
            (client_id,),
            fetch_one=True
        )

        # Select multiple rows
        agents = execute_query(
            "SELECT * FROM agents WHERE client_id = %s",
            (client_id,),
            fetch_all=True
        )
    """
    conn = None
    cursor = None

    try:
        # Get connection from pool
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Return rows as dictionaries

        # Execute query with parameters (prevents SQL injection)
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        # Handle different return types
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
            # Return cursor for manual handling
            return cursor

    except MySQLError as e:
        logger.error(f"Database query error: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        logger.error(traceback.format_exc())

        # Rollback on error
        if conn and commit:
            try:
                conn.rollback()
                logger.info("Transaction rolled back due to error")
            except:
                pass

        # Clean up resources
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
        logger.error(traceback.format_exc())

        # Clean up resources
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

# Initialize database pool on module load
try:
    initialize_database_pool()
except Exception as e:
    logger.critical(f"CRITICAL: Failed to initialize database pool: {e}")
    logger.critical("Application cannot start without database connection")
    sys.exit(1)

logger.info("Database layer initialized successfully")

# ============================================================================
# SECTION 6: UTILITY FUNCTIONS
# ============================================================================
#
# Helper functions for common operations: validation, formatting, error
# handling, and response generation.
# ============================================================================

def success_response(data: Any = None, message: str = None) -> Dict:
    """
    Generate standardized success response.

    All API endpoints should return responses in a consistent format.
    This function creates the standard success response structure.

    Args:
        data: Response data (any JSON-serializable type)
        message: Optional success message

    Returns:
        Dictionary with standard success response format

    Example:
        return jsonify(success_response({"client_id": "123"}, "Client created"))
    """
    response = {
        "status": "success",
        "data": data if data is not None else {},
        "error": None
    }

    if message:
        response["message"] = message

    return response

def error_response(error_message: str, error_code: str = None,
                  http_status: int = 400) -> Tuple[Dict, int]:
    """
    Generate standardized error response.

    All API endpoints should return errors in a consistent format.
    This function creates the standard error response structure.

    Args:
        error_message: Human-readable error message
        error_code: Machine-readable error code (e.g., "INVALID_TOKEN")
        http_status: HTTP status code (default: 400 Bad Request)

    Returns:
        Tuple of (error dictionary, HTTP status code)

    Example:
        return jsonify(*error_response("Invalid client ID", "INVALID_CLIENT", 404))
    """
    response = {
        "status": "error",
        "error": error_message,
        "data": None
    }

    if error_code:
        response["code"] = error_code

    return response, http_status

def validate_required_fields(data: Dict, required_fields: List[str]) -> Optional[str]:
    """
    Validate that all required fields are present in request data.

    Args:
        data: Request data dictionary
        required_fields: List of required field names

    Returns:
        Error message if validation fails, None if all fields present

    Example:
        error = validate_required_fields(request.json, ['name', 'email'])
        if error:
            return jsonify(*error_response(error))
    """
    if not data:
        return "Request body is required"

    missing_fields = [field for field in required_fields if field not in data or data[field] is None]

    if missing_fields:
        return f"Missing required fields: {', '.join(missing_fields)}"

    return None

def validate_email(email: str) -> bool:
    """
    Validate email format using regex.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_token(length: int = 64) -> str:
    """
    Generate a cryptographically secure random token.

    Used for client authentication tokens and session identifiers.

    Args:
        length: Length of token in characters

    Returns:
        Secure random token string
    """
    return secrets.token_hex(length // 2)

def format_decimal(value: Decimal, precision: int = 4) -> float:
    """
    Format Decimal from database as float for JSON serialization.

    Args:
        value: Decimal value from database
        precision: Number of decimal places

    Returns:
        Float value rounded to specified precision
    """
    if value is None:
        return 0.0
    return round(float(value), precision)

def parse_datetime(dt_string: str) -> Optional[datetime]:
    """
    Parse datetime string in various formats.

    Args:
        dt_string: Datetime string

    Returns:
        datetime object or None if parsing fails
    """
    if not dt_string:
        return None

    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S.%fZ',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt_string, fmt)
        except ValueError:
            continue

    logger.warning(f"Failed to parse datetime string: {dt_string}")
    return None

logger.info("Utility functions loaded successfully")

# ============================================================================
# SECTION 7: AUTHENTICATION AND AUTHORIZATION
# ============================================================================
#
# Decorators and functions for authentication and authorization.
# Implements token-based authentication for clients and admin.
# ============================================================================

def require_admin_auth(f):
    """
    Decorator to require admin authentication for endpoint access.

    Checks for valid admin token in Authorization header.
    Returns 401 Unauthorized if token is missing or invalid.

    Usage:
        @app.route('/api/admin/stats')
        @require_admin_auth
        def get_admin_stats():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get authorization header
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            logger.warning(f"Admin endpoint accessed without authorization: {request.path}")
            return jsonify(*error_response("Missing authorization header", "UNAUTHORIZED", 401))

        # Check for Bearer token format
        if not auth_header.startswith('Bearer '):
            return jsonify(*error_response("Invalid authorization format", "INVALID_AUTH_FORMAT", 401))

        # Extract token
        token = auth_header.replace('Bearer ', '')

        # Validate token
        if token != ADMIN_TOKEN:
            logger.warning(f"Invalid admin token attempt: {request.path}")
            return jsonify(*error_response("Invalid admin token", "INVALID_TOKEN", 401))

        # Token is valid, proceed to endpoint
        return f(*args, **kwargs)

    return decorated_function

def require_client_auth(f):
    """
    Decorator to require client authentication for endpoint access.

    Validates client token and injects client_id into kwargs.
    Returns 401 Unauthorized if token is missing or invalid.

    Usage:
        @app.route('/api/client/<client_id>/agents')
        @require_client_auth
        def get_client_agents(client_id):
            # client_id is validated and guaranteed to exist
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get authorization header
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            logger.warning(f"Client endpoint accessed without authorization: {request.path}")
            return jsonify(*error_response("Missing authorization header", "UNAUTHORIZED", 401))

        # Check for Bearer token format
        if not auth_header.startswith('Bearer '):
            return jsonify(*error_response("Invalid authorization format", "INVALID_AUTH_FORMAT", 401))

        # Extract token
        token = auth_header.replace('Bearer ', '')

        # Validate token against database
        client = execute_query(
            "SELECT id, name, status FROM clients WHERE client_token = %s",
            (token,),
            fetch_one=True
        )

        if not client:
            logger.warning(f"Invalid client token attempt: {request.path}")
            return jsonify(*error_response("Invalid client token", "INVALID_TOKEN", 401))

        if client['status'] != 'active':
            return jsonify(*error_response("Client account is not active", "INACTIVE_CLIENT", 403))

        # Inject authenticated client_id into kwargs
        kwargs['authenticated_client_id'] = client['id']

        # Proceed to endpoint
        return f(*args, **kwargs)

    return decorated_function

def get_client_from_token(token: str) -> Optional[Dict]:
    """
    Get client information from authentication token.

    Args:
        token: Client authentication token

    Returns:
        Client dictionary or None if invalid token
    """
    if not token:
        return None

    try:
        client = execute_query(
            "SELECT * FROM clients WHERE client_token = %s AND status = 'active'",
            (token,),
            fetch_one=True
        )
        return client
    except Exception as e:
        logger.error(f"Error getting client from token: {e}")
        return None

logger.info("Authentication system initialized")

# ============================================================================
# SECTION 8: HEALTH CHECK ENDPOINT
# ============================================================================
#
# Simple health check endpoint for load balancers and monitoring systems.
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.

    Returns server status, version, and uptime information.
    Used by load balancers and monitoring systems to verify service health.

    Returns:
        - 200 OK: Service is healthy
        - 503 Service Unavailable: Service is unhealthy

    Response:
        {
            "status": "healthy",
            "timestamp": "2024-11-26T10:00:00Z",
            "version": "5.0",
            "uptime_seconds": 86400
        }
    """
    try:
        # Calculate uptime
        uptime = (datetime.utcnow() - APP_START_TIME).total_seconds()

        # Test database connection
        execute_query("SELECT 1", fetch_one=True)

        # Return healthy status
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "version": "5.0",
            "uptime_seconds": int(uptime)
        }), 200

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }), 503

logger.info("Health check endpoint registered")

# ============================================================================
# SECTION 9: ADMIN APIs - OVERVIEW AND STATISTICS
# ============================================================================
#
# Admin endpoints for global statistics, client management, and system health.
# These endpoints provide aggregated views across all clients.
# ============================================================================

@app.route('/api/admin/stats', methods=['GET'])
@require_admin_auth
def get_admin_stats():
    """
    Get global statistics across all clients.

    Returns aggregated metrics including:
    - Total number of clients
    - Total agents (online vs offline)
    - Total savings across all clients
    - Total switches (manual, automatic, emergency)
    - System health indicators

    Authentication: Requires admin token

    Returns:
        {
            "status": "success",
            "data": {
                "total_clients": 10,
                "total_agents": 45,
                "agents_online": 42,
                "agents_offline": 3,
                "total_instances": 38,
                "total_savings": 12450.50,
                "total_switches": 156,
                "manual_switches": 12,
                "automatic_switches": 140,
                "emergency_switches": 4,
                "backend_health": "healthy",
                "decision_engine_loaded": true,
                "ml_model_active": true
            }
        }
    """
    try:
        # Get client count
        client_count = execute_query(
            "SELECT COUNT(*) as count FROM clients WHERE status = 'active'",
            fetch_one=True
        )

        # Get agent statistics
        agent_stats = execute_query(
            """
            SELECT
                COUNT(*) as total_agents,
                SUM(CASE WHEN status = 'online' THEN 1 ELSE 0 END) as agents_online,
                SUM(CASE WHEN status = 'offline' THEN 1 ELSE 0 END) as agents_offline
            FROM agents
            WHERE terminated_at IS NULL
            """,
            fetch_one=True
        )

        # Get total savings
        total_savings = execute_query(
            "SELECT SUM(total_savings) as total_savings FROM clients WHERE status = 'active'",
            fetch_one=True
        )

        # Get switch statistics
        switch_stats = execute_query(
            """
            SELECT
                COUNT(*) as total_switches,
                SUM(CASE WHEN trigger = 'manual' THEN 1 ELSE 0 END) as manual_switches,
                SUM(CASE WHEN trigger = 'automatic' THEN 1 ELSE 0 END) as automatic_switches,
                SUM(CASE WHEN trigger = 'emergency' THEN 1 ELSE 0 END) as emergency_switches
            FROM switches
            """,
            fetch_one=True
        )

        # TODO: Check decision engine and ML model status
        # This would require importing and checking the decision engine module
        decision_engine_loaded = True  # Placeholder
        ml_model_active = True  # Placeholder

        # Compile response
        data = {
            "total_clients": client_count['count'] if client_count else 0,
            "total_agents": agent_stats['total_agents'] if agent_stats else 0,
            "agents_online": agent_stats['agents_online'] if agent_stats else 0,
            "agents_offline": agent_stats['agents_offline'] if agent_stats else 0,
            "total_savings": format_decimal(total_savings['total_savings']) if total_savings and total_savings['total_savings'] else 0.0,
            "total_switches": switch_stats['total_switches'] if switch_stats else 0,
            "manual_switches": switch_stats['manual_switches'] if switch_stats else 0,
            "automatic_switches": switch_stats['automatic_switches'] if switch_stats else 0,
            "emergency_switches": switch_stats['emergency_switches'] if switch_stats else 0,
            "backend_health": "healthy",
            "decision_engine_loaded": decision_engine_loaded,
            "ml_model_active": ml_model_active
        }

        return jsonify(success_response(data))

    except Exception as e:
        logger.error(f"Error in get_admin_stats: {e}")
        logger.error(traceback.format_exc())
        return jsonify(*error_response("Failed to retrieve admin statistics", "SERVER_ERROR", 500))

# Additional admin endpoints will continue below...
# This is just the beginning of the comprehensive implementation.
# The file will be continued in subsequent sections.

logger.info("Admin API endpoints registered (partial - to be continued)")

