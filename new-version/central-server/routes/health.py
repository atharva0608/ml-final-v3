"""
Health Check Routes
Provides system health and status endpoints.
"""

import logging
from datetime import datetime
from flask import Blueprint, jsonify
from core.database import execute_query

logger = logging.getLogger(__name__)

# Create Blueprint
health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.

    Returns system health status, database connectivity, and basic metrics.
    Used by load balancers and monitoring systems to check if the service is running.

    Returns:
        200: Service is healthy
        500: Service is unhealthy
    """
    try:
        # Test database connectivity
        execute_query("SELECT 1", fetch_one=True)

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'database': 'connected'
        })

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 500
