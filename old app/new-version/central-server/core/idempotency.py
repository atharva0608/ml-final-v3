"""
Idempotency handling for agent commands.

Provides decorator and utilities for request_id based duplicate prevention.
All agent commands should use X-Request-ID header or request_id in body
to enable safe retries without duplicate execution.
"""
import logging
from functools import wraps
from flask import request, jsonify
from core.database import execute_query
from core.utils import error_response, success_response

logger = logging.getLogger(__name__)


def require_idempotency_key(f):
    """
    Decorator to enforce request_id based idempotency.

    Checks for X-Request-ID header or request_id in JSON body.
    Returns cached response if request already processed.

    Usage:
        @app.route('/api/action', methods=['POST'])
        @require_idempotency_key
        def perform_action():
            # Access idempotency key via request.request_id
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract request_id from header or body
        request_id = request.headers.get('X-Request-ID')

        if not request_id and request.json:
            request_id = request.json.get('request_id')

        if not request_id:
            logger.warning(f"Request to {request.path} missing idempotency key")
            return jsonify(*error_response(
                "Missing request_id for idempotency. "
                "Provide X-Request-ID header or request_id in body.",
                "MISSING_REQUEST_ID",
                400
            ))

        # Check if already processed
        existing = execute_query(
            "SELECT status, execution_result, message FROM commands WHERE request_id = %s",
            (request_id,),
            fetch_one=True
        )

        if existing:
            status = existing['status']

            if status == 'completed':
                logger.info(f"Returning cached response for request_id={request_id}")
                result = existing['execution_result']

                # Try to parse JSON result
                if result:
                    try:
                        import json
                        result = json.loads(result) if isinstance(result, str) else result
                    except:
                        pass

                return jsonify(success_response({
                    'cached': True,
                    'result': result,
                    'message': existing.get('message', 'Command already completed')
                }))

            elif status == 'failed':
                logger.info(f"Returning cached failure for request_id={request_id}")
                return jsonify(*error_response(
                    existing.get('message', 'Previous execution failed'),
                    "IDEMPOTENT_FAILURE",
                    500
                ))

            elif status in ('pending', 'executing'):
                # Still processing
                logger.warning(f"Duplicate request detected: request_id={request_id}, status={status}")
                return jsonify(*error_response(
                    "Request already in progress. Please wait for completion.",
                    "DUPLICATE_REQUEST",
                    409
                ))

        # Store request_id in request context for use in endpoint
        request.request_id = request_id

        # Proceed with original function
        return f(*args, **kwargs)

    return decorated_function


def check_idempotency(request_id: str) -> dict:
    """
    Check if request_id has been processed.

    Returns:
        dict with keys:
            - exists: bool
            - status: str (if exists)
            - result: any (if completed)
    """
    if not request_id:
        return {'exists': False}

    existing = execute_query(
        "SELECT status, execution_result, message FROM commands WHERE request_id = %s",
        (request_id,),
        fetch_one=True
    )

    if not existing:
        return {'exists': False}

    return {
        'exists': True,
        'status': existing['status'],
        'result': existing.get('execution_result'),
        'message': existing.get('message')
    }


def register_idempotent_command(
    request_id: str,
    command_type: str,
    agent_id: str,
    client_id: str,
    **kwargs
) -> str:
    """
    Register a new command with idempotency key.

    Returns command_id.
    """
    from core.utils import generate_uuid

    command_id = generate_uuid()

    execute_query("""
        INSERT INTO commands
        (id, request_id, command_type, agent_id, client_id,
         status, created_at, target_pool_id, target_mode,
         priority, trigger_type, created_by)
        VALUES (%s, %s, %s, %s, %s, 'pending', NOW(), %s, %s, %s, %s, %s)
    """, (
        command_id,
        request_id,
        command_type,
        agent_id,
        client_id,
        kwargs.get('target_pool_id'),
        kwargs.get('target_mode'),
        kwargs.get('priority', 25),
        kwargs.get('trigger_type', 'api'),
        kwargs.get('created_by')
    ), commit=True)

    logger.info(f"Registered idempotent command: command_id={command_id}, request_id={request_id}")

    return command_id


def mark_command_completed(command_id: str, result: dict, message: str = None):
    """Mark command as completed with result."""
    import json

    execute_query("""
        UPDATE commands
        SET status = 'completed',
            success = TRUE,
            execution_result = %s,
            message = %s,
            completed_at = NOW()
        WHERE id = %s
    """, (json.dumps(result), message, command_id), commit=True)

    logger.info(f"Marked command {command_id} as completed")


def mark_command_failed(command_id: str, error_message: str):
    """Mark command as failed with error message."""
    execute_query("""
        UPDATE commands
        SET status = 'failed',
            success = FALSE,
            message = %s,
            completed_at = NOW()
        WHERE id = %s
    """, (error_message, command_id), commit=True)

    logger.error(f"Marked command {command_id} as failed: {error_message}")
