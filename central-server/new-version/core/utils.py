"""
Utility functions for common operations.
Provides validation, formatting, error handling, and response generation.
"""

import secrets
import re
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime


def success_response(data: Any = None, message: str = None) -> Dict:
    """Generate standardized success response."""
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
    """Generate standardized error response."""
    response = {
        "status": "error",
        "error": error_message,
        "data": None
    }

    if error_code:
        response["code"] = error_code

    return response, http_status


def validate_required_fields(data: Dict, required_fields: List[str]) -> Optional[str]:
    """Validate that all required fields are present in request data."""
    if not data:
        return "Request body is required"

    missing_fields = [field for field in required_fields if field not in data or data[field] is None]

    if missing_fields:
        return f"Missing required fields: {', '.join(missing_fields)}"

    return None


def validate_email(email: str) -> bool:
    """Validate email format using regex."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def generate_token(length: int = 64) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_hex(length // 2)


def format_decimal(value: Decimal, precision: int = 4) -> float:
    """Format Decimal from database as float for JSON serialization."""
    if value is None:
        return 0.0
    return round(float(value), precision)


def parse_datetime(dt_string: str) -> Optional[datetime]:
    """Parse datetime string in various formats."""
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

    return None


def generate_uuid() -> str:
    """Generate a UUID string for database entities."""
    import uuid
    return str(uuid.uuid4())


def generate_client_token(length: int = 64) -> str:
    """
    Generate a secure client authentication token.

    Args:
        length: Length of the token (default 64 characters)

    Returns:
        Hex string token
    """
    return generate_token(length)


def log_system_event(event_type: str, severity: str, message: str,
                     client_id: str = None, agent_id: str = None,
                     metadata: Dict = None) -> None:
    """
    Log system event to database.

    Args:
        event_type: Type of event (e.g., 'agent_registered', 'switch_completed')
        severity: Event severity ('info', 'warning', 'error', 'critical')
        message: Human-readable message
        client_id: Optional client ID
        agent_id: Optional agent ID
        metadata: Optional metadata dictionary
    """
    import json
    from .database import execute_query

    try:
        execute_query("""
            INSERT INTO system_events
            (event_type, severity, message, client_id, agent_id, metadata, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (
            event_type,
            severity,
            message,
            client_id,
            agent_id,
            json.dumps(metadata) if metadata else None
        ), commit=True)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to log system event: {e}")


def create_notification(message: str, notification_type: str,
                       client_id: str) -> None:
    """
    Create a notification for a client.

    Args:
        message: Notification message
        notification_type: Type of notification ('info', 'warning', 'error', 'success')
        client_id: Client ID to send notification to
    """
    from .database import execute_query

    try:
        execute_query("""
            INSERT INTO notifications
            (client_id, message, notification_type, is_read, created_at)
            VALUES (%s, %s, %s, FALSE, NOW())
        """, (client_id, message, notification_type), commit=True)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create notification: {e}")
