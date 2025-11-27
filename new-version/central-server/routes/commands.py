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
    """Get pending commands for agent (sorted by priority, immediate commands first)"""
    try:
        # Check both commands table and pending_switch_commands for compatibility
        # Includes new command types: LAUNCH_INSTANCE, TERMINATE_INSTANCE
        commands = execute_query("""
            SELECT
                CAST(id AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as id,
                CAST(instance_id AS CHAR(64) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as instance_id,
                CAST(command_type AS CHAR(50) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as command_type,
                CAST(target_mode AS CHAR(20) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as target_mode,
                CAST(target_pool_id AS CHAR(128) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as target_pool_id,
                CAST(request_id AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as request_id,
                priority,
                terminate_wait_seconds,
                metadata,
                created_at
            FROM commands
            WHERE agent_id = %s AND status = 'pending'

            UNION ALL

            SELECT
                CAST(id AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as id,
                CAST(instance_id AS CHAR(64) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as instance_id,
                'switch' as command_type,
                CAST(target_mode AS CHAR(20) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as target_mode,
                CAST(target_pool_id AS CHAR(128) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci as target_pool_id,
                NULL as request_id,
                priority,
                terminate_wait_seconds,
                NULL as metadata,
                created_at
            FROM pending_switch_commands
            WHERE agent_id = %s AND executed_at IS NULL

            ORDER BY priority DESC, created_at ASC
        """, (agent_id, agent_id), fetch=True)

        formatted_commands = []
        for cmd in commands or []:
            metadata = {}
            if cmd.get('metadata'):
                try:
                    metadata = json.loads(cmd['metadata']) if isinstance(cmd['metadata'], str) else cmd['metadata']
                except:
                    metadata = {}

            formatted_commands.append({
                'id': str(cmd['id']),
                'command_type': cmd.get('command_type', 'switch'),
                'instance_id': cmd['instance_id'],
                'target_mode': cmd['target_mode'],
                'target_pool_id': cmd['target_pool_id'],
                'request_id': cmd.get('request_id'),
                'priority': cmd['priority'],
                'terminate_wait_seconds': cmd['terminate_wait_seconds'],
                'metadata': metadata,
                'created_at': cmd['created_at'].isoformat() if cmd['created_at'] else None
            })

        return jsonify(formatted_commands)

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
