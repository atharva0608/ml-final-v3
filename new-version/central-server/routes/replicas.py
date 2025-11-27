from flask import Blueprint, request, jsonify
import logging
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import success_response, error_response, format_decimal
import json
from datetime import datetime

logger = logging.getLogger(__name__)
replicas_bp = Blueprint('replicas', __name__)

@replicas_bp.route('/api/client/<client_id>/replicas', methods=['GET'])
def get_client_replicas(client_id: str):
    """Get all instances with active replicas for a client"""
    try:
        # Check if replica_instances table exists
        table_exists = execute_query("""
            SELECT COUNT(*) as count
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_name = 'replica_instances'
        """, fetch_one=True)

        if not table_exists or table_exists.get('count', 0) == 0:
            logger.info("replica_instances table does not exist yet, returning empty list")
            return jsonify([])

        # Get all active replicas with their parent instance and agent info
        replicas = execute_query("""
            SELECT
                ri.id as replica_id,
                ri.instance_id as replica_instance_id,
                ri.replica_type,
                ri.pool_id,
                ri.status as replica_status,
                ri.sync_status,
                ri.sync_latency_ms,
                ri.state_transfer_progress,
                ri.hourly_cost,
                ri.total_cost,
                ri.created_by,
                ri.created_at as replica_created_at,
                ri.ready_at as replica_ready_at,
                ri.terminated_at as replica_terminated_at,
                ri.is_active as replica_is_active,
                sp.pool_name,
                sp.instance_type as pool_instance_type,
                sp.region as pool_region,
                sp.az as pool_az,
                a.id as agent_id,
                a.instance_id as primary_instance_id,
                i.instance_type as primary_instance_type,
                i.region as primary_region,
                i.az as primary_az,
                i.current_mode as primary_mode
            FROM replica_instances ri
            LEFT JOIN spot_pools sp ON ri.pool_id = sp.id
            JOIN agents a ON ri.agent_id = a.id
            LEFT JOIN instances i ON a.instance_id = i.id
            WHERE a.client_id = %s
              AND ri.is_active = TRUE
              AND ri.status NOT IN ('terminated', 'promoted')
            ORDER BY ri.created_at DESC
        """, (client_id,), fetch=True)

        result = []
        for r in (replicas or []):
            result.append({
                'agentId': r['agent_id'],
                'primary': {
                    'instanceId': r['primary_instance_id'],
                    'instanceType': r['primary_instance_type'],
                    'region': r['primary_region'],
                    'az': r['primary_az'],
                    'mode': r['primary_mode']
                },
                'replica': {
                    'id': r['replica_id'],
                    'instanceId': r['replica_instance_id'],
                    'type': r['replica_type'],
                    'status': r['replica_status'],
                    'sync_status': r['sync_status'],
                    'sync_latency_ms': r['sync_latency_ms'],
                    'state_transfer_progress': float(r['state_transfer_progress']) if r['state_transfer_progress'] else 0.0,
                    'pool': {
                        'id': r['pool_id'],
                        'name': r['pool_name'],
                        'instance_type': r['pool_instance_type'],
                        'region': r['pool_region'],
                        'az': r['pool_az']
                    } if r['pool_id'] else None,
                    'cost': {
                        'hourly': float(r['hourly_cost']) if r['hourly_cost'] else None,
                        'total': float(r['total_cost']) if r['total_cost'] else 0.0
                    },
                    'created_by': r['created_by'],
                    'created_at': r['replica_created_at'].isoformat() if r['replica_created_at'] else None,
                    'ready_at': r['replica_ready_at'].isoformat() if r['replica_ready_at'] else None,
                    'terminated_at': r['replica_terminated_at'].isoformat() if r['replica_terminated_at'] else None,
                    'is_active': bool(r['replica_is_active'])
                }
            })

        return jsonify(result)

    except Exception as e:
        logger.error(f"Get client replicas error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
