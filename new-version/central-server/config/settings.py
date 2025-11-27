"""
Configuration settings for AWS Spot Optimizer Backend v5.0
All environment variables and constants are defined here.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_DATABASE = os.getenv('DB_DATABASE', 'spot_optimizer')
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))
DB_POOL_NAME = os.getenv('DB_POOL_NAME', 'spot_optimizer_pool')

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'admin-secret-token-change-in-production')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')
SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-secret-key-in-production')

# ============================================================================
# PATHS CONFIGURATION
# ============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISION_ENGINE_DIR = os.getenv('DECISION_ENGINE_DIR', os.path.join(BASE_DIR, 'decision_engines'))
MODEL_DIR = os.getenv('MODEL_DIR', os.path.join(BASE_DIR, 'models'))
LOG_DIR = os.getenv('LOG_DIR', os.path.join(BASE_DIR, 'logs'))

# Create directories if they don't exist
for directory in [DECISION_ENGINE_DIR, MODEL_DIR, LOG_DIR]:
    os.makedirs(directory, exist_ok=True)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# ============================================================================
# AGENT CONFIGURATION
# ============================================================================
AGENT_HEARTBEAT_TIMEOUT = int(os.getenv('AGENT_HEARTBEAT_TIMEOUT', '120'))
DEFAULT_TERMINATE_WAIT_SECONDS = int(os.getenv('DEFAULT_TERMINATE_WAIT_SECONDS', '300'))

# ============================================================================
# BACKGROUND JOBS CONFIGURATION
# ============================================================================
ENABLE_BACKGROUND_JOBS = os.getenv('ENABLE_BACKGROUND_JOBS', 'True').lower() == 'true'

# ============================================================================
# APPLICATION METADATA
# ============================================================================
APP_NAME = 'AWS Spot Optimizer Backend'
APP_VERSION = '5.0'
APP_DESCRIPTION = 'Central Server for AWS Spot Instance Optimization'
