"""
Authentication and authorization decorators and functions.
Provides token-based authentication for clients and admin.
"""

import logging
from functools import wraps
from flask import request, jsonify
from config.settings import ADMIN_TOKEN
from .database import execute_query
from .utils import error_response

logger = logging.getLogger(__name__)


def require_admin_auth(f):
    """Decorator to require admin authentication for endpoint access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            logger.warning(f"Admin endpoint accessed without authorization: {request.path}")
            return jsonify(*error_response("Missing authorization header", "UNAUTHORIZED", 401))

        if not auth_header.startswith('Bearer '):
            return jsonify(*error_response("Invalid authorization format", "INVALID_AUTH_FORMAT", 401))

        token = auth_header.replace('Bearer ', '')

        if token != ADMIN_TOKEN:
            logger.warning(f"Invalid admin token attempt: {request.path}")
            return jsonify(*error_response("Invalid admin token", "INVALID_TOKEN", 401))

        return f(*args, **kwargs)

    return decorated_function


def require_client_auth(f):
    """
    Decorator to require client authentication for endpoint access.

    Injects authenticated_client_id into kwargs and also sets request.client_id
    for backward compatibility with legacy code.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            logger.warning(f"Client endpoint accessed without authorization: {request.path}")
            return jsonify(*error_response("Missing authorization header", "UNAUTHORIZED", 401))

        if not auth_header.startswith('Bearer '):
            return jsonify(*error_response("Invalid authorization format", "INVALID_AUTH_FORMAT", 401))

        token = auth_header.replace('Bearer ', '')

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

        # Inject into kwargs for new code
        kwargs['authenticated_client_id'] = client['id']

        # Also set on request object for legacy code compatibility
        request.client_id = client['id']
        request.client_name = client['name']

        return f(*args, **kwargs)

    return decorated_function


def get_client_from_token(token: str):
    """Get client information from authentication token."""
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
