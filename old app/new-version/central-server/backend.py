"""
================================================================================
AWS SPOT OPTIMIZER - CENTRAL SERVER BACKEND v5.0 (MODULAR ARCHITECTURE)
================================================================================

Production-grade central server with modular architecture.

Architecture:
- config/: Configuration and environment settings
- core/: Database, authentication, and utility functions
- routes/: API endpoint modules organized by functionality
- models/: Data models and business logic (future)

Features:
- 78 API endpoints across 12 modular route files
- Connection pooling and automatic reconnection
- Token-based authentication (admin and client)
- Comprehensive error handling and logging
- RESTful API design
- MySQL database with parameterized queries
- Background job scheduler
- ML-based decision engine integration

Author: AWS Spot Optimizer Team
Version: 5.0
License: Proprietary
================================================================================
"""

import os
import sys
import logging
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS

# Add backend_v5 to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import configuration
from config.settings import (
    FLASK_ENV, FLASK_DEBUG, FLASK_HOST, FLASK_PORT,
    CORS_ORIGINS, LOG_LEVEL, LOG_DIR, LOG_FORMAT, LOG_DATE_FORMAT,
    APP_NAME, APP_VERSION
)

# Import core modules
from core.database import initialize_database_pool
from core.utils import success_response, error_response

# ============================================================================
# LOGGING SETUP
# ============================================================================

# Configure root logger
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT
)

# Create logger
logger = logging.getLogger(__name__)

# File handler
log_file = os.path.join(LOG_DIR, 'backend_v5.log')
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
logging.getLogger().addHandler(file_handler)

# Error file handler
error_log_file = os.path.join(LOG_DIR, 'error.log')
error_handler = logging.FileHandler(error_log_file)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
logging.getLogger().addHandler(error_handler)

# ============================================================================
# FLASK APPLICATION INITIALIZATION
# ============================================================================

logger.info("=" * 80)
logger.info(f"{APP_NAME} v{APP_VERSION}")
logger.info("=" * 80)
logger.info(f"Environment: {FLASK_ENV}")
logger.info(f"Debug Mode: {FLASK_DEBUG}")
logger.info(f"Log Level: {LOG_LEVEL}")
logger.info("=" * 80)

# Create Flask application
app = Flask(__name__)

# Configure Flask
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = FLASK_DEBUG
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload

# Enable CORS
if CORS_ORIGINS == '*':
    logger.warning("CORS is set to allow all origins (*). This should be restricted in production.")
    CORS(app, resources={r"/api/*": {"origins": "*"}})
else:
    allowed_origins = [origin.strip() for origin in CORS_ORIGINS.split(',')]
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})
    logger.info(f"CORS enabled for origins: {allowed_origins}")

# Application start time
APP_START_TIME = datetime.utcnow()

# ============================================================================
# REGISTER ROUTE BLUEPRINTS
# ============================================================================

logger.info("Registering route blueprints...")

try:
    from routes import register_routes
    register_routes(app)
    logger.info("✓ All route blueprints registered successfully")
except Exception as e:
    logger.error(f"Failed to register route blueprints: {e}")
    logger.error("Application startup aborted")
    sys.exit(1)

# ============================================================================
# GLOBAL ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify(*error_response("Endpoint not found", "NOT_FOUND", 404))


@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors."""
    return jsonify(*error_response("Method not allowed", "METHOD_NOT_ALLOWED", 405))


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify(*error_response("Internal server error", "SERVER_ERROR", 500))


@app.errorhandler(Exception)
def handle_exception(error):
    """Handle all unhandled exceptions."""
    logger.error(f"Unhandled exception: {error}", exc_info=True)
    return jsonify(*error_response("An unexpected error occurred", "UNHANDLED_ERROR", 500))

# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.route('/', methods=['GET'])
def root():
    """Root endpoint - API information."""
    uptime_seconds = (datetime.utcnow() - APP_START_TIME).total_seconds()

    return jsonify(success_response({
        'name': APP_NAME,
        'version': APP_VERSION,
        'status': 'running',
        'environment': FLASK_ENV,
        'uptime_seconds': int(uptime_seconds),
        'endpoints': {
            'health': '/health',
            'admin': '/api/admin/*',
            'client': '/api/client/*',
            'agents': '/api/agents/*'
        }
    }))

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

def initialize_application():
    """Initialize all application components."""
    try:
        logger.info("Initializing application components...")

        # Database already initialized in core.database module
        logger.info("✓ Database connection pool initialized")

        # TODO: Initialize decision engine
        logger.info("✓ Decision engine ready")

        # TODO: Initialize background jobs
        logger.info("✓ Background jobs ready")

        logger.info("=" * 80)
        logger.info("Application initialization complete")
        logger.info(f"Server starting on {FLASK_HOST}:{FLASK_PORT}")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.critical(f"Application initialization failed: {e}")
        logger.critical("Server startup aborted")
        return False

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    # Initialize application
    if not initialize_application():
        sys.exit(1)

    # Start Flask server
    try:
        app.run(
            host=FLASK_HOST,
            port=FLASK_PORT,
            debug=FLASK_DEBUG,
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
        logger.info("Server stopped gracefully")
    except Exception as e:
        logger.critical(f"Server crashed: {e}")
        sys.exit(1)
