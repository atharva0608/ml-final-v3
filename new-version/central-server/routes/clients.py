from flask import Blueprint, request, jsonify
import logging
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import success_response, error_response, format_decimal
import json
from datetime import datetime

logger = logging.getLogger(__name__)
clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/api/client/validate', methods=['GET'])
def validate_client_token():
    """Validate client token for frontend authentication"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'valid': False, 'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header.replace('Bearer ', '').strip()

        if not token:
            return jsonify({'valid': False, 'error': 'Token is empty'}), 401

        # Validate token against database
        client = execute_query("""
            SELECT id, name, email, is_active, status
            FROM clients
            WHERE client_token = %s
        """, (token,), fetch_one=True)

        if not client:
            return jsonify({'valid': False, 'error': 'Invalid token'}), 401

        if not client['is_active'] or client['status'] != 'active':
            return jsonify({'valid': False, 'error': 'Client account is not active'}), 403

        # Log validation attempt
        logger.info(f"Client token validated successfully for client {client['id']}")

        return jsonify({
            'valid': True,
            'client_id': client['id'],
            'name': client['name'],
            'email': client['email']
        })

    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return jsonify({'valid': False, 'error': 'Internal server error'}), 500

@clients_bp.route('/api/client/<client_id>', methods=['GET'])
def get_client_details(client_id: str):
    """Get client overview"""
    try:
        client = execute_query("""
            SELECT
                c.*,
                COUNT(DISTINCT CASE WHEN a.status = 'online' THEN a.id END) as agents_online,
                COUNT(DISTINCT a.id) as agents_total,
                COUNT(DISTINCT CASE WHEN i.is_active = TRUE THEN i.id END) as instances
            FROM clients c
            LEFT JOIN agents a ON a.client_id = c.id
            LEFT JOIN instances i ON i.client_id = c.id
            WHERE c.id = %s
            GROUP BY c.id
        """, (client_id,), fetch_one=True)

        if not client:
            return jsonify({'error': 'Client not found'}), 404

        return jsonify({
            'id': client['id'],
            'name': client['name'],
            'status': 'active' if client['is_active'] else 'inactive',
            'agentsOnline': client['agents_online'] or 0,
            'agentsTotal': client['agents_total'] or 0,
            'instances': client['instances'] or 0,
            'totalSavings': float(client['total_savings'] or 0),
            'lastSync': client['last_sync_at'].isoformat() if client['last_sync_at'] else None
        })

    except Exception as e:
        logger.error(f"Get client details error: {e}")
        return jsonify({'error': str(e)}), 500

@clients_bp.route('/api/client/<client_id>/agents', methods=['GET'])
def get_client_agents(client_id: str):
    """Get all active agents for client (excludes deleted agents)"""
    try:
        # Exclude deleted agents by default
        agents = execute_query("""
            SELECT a.*, ac.min_savings_percent, ac.risk_threshold,
                   ac.max_switches_per_week, ac.min_pool_duration_hours
            FROM agents a
            LEFT JOIN agent_configs ac ON ac.agent_id = a.id
            WHERE a.client_id = %s AND a.status != 'deleted'
            ORDER BY a.last_heartbeat_at DESC
        """, (client_id,), fetch=True)

        return jsonify([{
            'id': agent['id'],
            'logicalAgentId': agent['logical_agent_id'],
            'instanceId': agent['instance_id'],
            'instanceType': agent['instance_type'],
            'region': agent['region'],
            'az': agent['az'],
            'currentMode': agent['current_mode'],
            'status': agent['status'],
            'lastHeartbeat': agent['last_heartbeat_at'].isoformat() if agent['last_heartbeat_at'] else None,
            'instanceCount': agent['instance_count'] or 0,
            'enabled': agent['enabled'],
            'autoSwitchEnabled': agent['auto_switch_enabled'],
            'manualReplicaEnabled': agent['manual_replica_enabled'],
            'autoTerminateEnabled': agent['auto_terminate_enabled'],
            'terminateWaitMinutes': (agent['terminate_wait_seconds'] or 1800) // 60,
            'agentVersion': agent['agent_version']
        } for agent in agents or []])

    except Exception as e:
        logger.error(f"Get agents error: {e}")
        return jsonify({'error': str(e)}), 500
