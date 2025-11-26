from flask import Blueprint, request, jsonify
import logging
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import success_response, error_response, format_decimal
import json
from datetime import datetime

logger = logging.getLogger(__name__)
commands_bp = Blueprint('commands', __name__)

@commands_bp.route('/api/agents/<agent_id>/pending-commands', methods=['GET'])
@require_client_auth
def get_pending_commands(agent_id: str):
    """Get pending commands for agent (sorted by priority)"""
    try:
        # Check both commands table and pending_switch_commands for compatibility
        commands = execute_query("""
            SELECT
                CAST(id AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as id,
                CAST(instance_id AS CHAR(64) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as instance_id,
                CAST(target_mode AS CHAR(20) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as target_mode,
                CAST(target_pool_id AS CHAR(128) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as target_pool_id,
                priority,
                terminate_wait_seconds,
                created_at
            FROM commands
            WHERE agent_id = %s AND status = 'pending'

            UNION ALL

            SELECT
                CAST(id AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as id,
                CAST(instance_id AS CHAR(64) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as instance_id,
                CAST(target_mode AS CHAR(20) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as target_mode,
                CAST(target_pool_id AS CHAR(128) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as target_pool_id,
                priority,
                terminate_wait_seconds,
                created_at
            FROM pending_switch_commands
            WHERE agent_id = %s AND executed_at IS NULL

            ORDER BY priority DESC, created_at ASC
        """, (agent_id, agent_id), fetch=True)

        return jsonify([{
            'id': str(cmd['id']),
            'instance_id': cmd['instance_id'],
            'target_mode': cmd['target_mode'],
            'target_pool_id': cmd['target_pool_id'],
            'priority': cmd['priority'],
            'terminate_wait_seconds': cmd['terminate_wait_seconds'],
            'created_at': cmd['created_at'].isoformat() if cmd['created_at'] else None
        } for cmd in commands or []])

    except Exception as e:
        logger.error(f"Get pending commands error: {e}")
        return jsonify({'error': str(e)}), 500

@commands_bp.route('/api/agents/<agent_id>/commands/<command_id>/executed', methods=['POST'])
@require_client_auth
def mark_command_executed(agent_id: str, command_id: str):
    """Mark command as executed"""
    data = request.json or {}

    try:
        success = data.get('success', True)
        message = data.get('message', '')

        # Try to update in commands table first
        execute_query("""
            UPDATE commands
            SET status = %s,
                success = %s,
                message = %s,
                executed_at = NOW(),
                completed_at = NOW()
            WHERE id = %s AND agent_id = %s
        """, (
            'completed' if success else 'failed',
            success,
            message,
            command_id,
            agent_id
        ))

        # Also try pending_switch_commands for backwards compatibility
        if command_id.isdigit():
            execute_query("""
                UPDATE pending_switch_commands
                SET executed_at = NOW(),
                    execution_result = %s
                WHERE id = %s AND agent_id = %s
            """, (json.dumps(data), int(command_id), agent_id))

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Mark command executed error: {e}")
        return jsonify({'error': str(e)}), 500
