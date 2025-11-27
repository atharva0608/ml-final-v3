from flask import Blueprint, request, jsonify
import logging
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import success_response, error_response, format_decimal, generate_uuid, generate_client_token, create_notification, log_system_event
import json
from datetime import datetime
import config
from pathlib import Path

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/admin/clients/create', methods=['POST'])
def create_client():
    """Create a new client with auto-generated token"""
    data = request.json or {}

    client_name = data.get('name', '').strip()
    if not client_name:
        return jsonify({'error': 'Client name is required'}), 400

    try:
        # Check if exists
        existing = execute_query(
            "SELECT id FROM clients WHERE name = %s",
            (client_name,),
            fetch_one=True
        )

        if existing:
            return jsonify({'error': f'Client "{client_name}" already exists'}), 409

        client_id = generate_uuid()
        client_token = generate_client_token()
        email = data.get('email', f"{client_name.lower().replace(' ', '_')}@example.com")

        execute_query("""
            INSERT INTO clients (id, name, email, client_token, is_active, status, total_savings)
            VALUES (%s, %s, %s, %s, TRUE, 'active', 0.0000)
        """, (client_id, client_name, email, client_token))

        create_notification(f"New client created: {client_name}", 'info', client_id)
        log_system_event('client_created', 'info', f"Client {client_name} created",
                        client_id=client_id, metadata={'client_name': client_name})

        logger.info(f"✓ New client created: {client_name} ({client_id})")

        return jsonify({
            'success': True,
            'client': {
                'id': client_id,
                'name': client_name,
                'token': client_token,
                'status': 'active'
            }
        })

    except Exception as e:
        logger.error(f"Create client error: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/clients/<client_id>', methods=['DELETE'])
def delete_client(client_id: str):
    """Delete a client and all associated data"""
    try:
        client = execute_query(
            "SELECT id, name FROM clients WHERE id = %s",
            (client_id,),
            fetch_one=True
        )

        if not client:
            return jsonify({'error': 'Client not found'}), 404

        client_name = client['name']

        execute_query("DELETE FROM clients WHERE id = %s", (client_id,))

        log_system_event('client_deleted', 'warning',
                        f"Client {client_name} ({client_id}) deleted permanently",
                        metadata={'deleted_client_id': client_id, 'deleted_client_name': client_name})

        logger.warning(f"⚠ Client deleted: {client_name} ({client_id})")

        return jsonify({
            'success': True,
            'message': f"Client '{client_name}' and all associated data have been deleted"
        })

    except Exception as e:
        logger.error(f"Delete client error: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/clients/<client_id>/regenerate-token', methods=['POST'])
def regenerate_client_token(client_id: str):
    """Regenerate client token"""
    try:
        client = execute_query(
            "SELECT id, name FROM clients WHERE id = %s",
            (client_id,),
            fetch_one=True
        )

        if not client:
            return jsonify({'error': 'Client not found'}), 404

        new_token = generate_client_token()

        execute_query(
            "UPDATE clients SET client_token = %s WHERE id = %s",
            (new_token, client_id)
        )

        create_notification(
            f"API token regenerated for client: {client['name']}. All agents need new token.",
            'warning',
            client_id
        )

        log_system_event('token_regenerated', 'warning',
                        f"Token regenerated for {client['name']}",
                        client_id=client_id)

        return jsonify({
            'success': True,
            'token': new_token,
            'message': 'Token regenerated successfully. Update all agents with the new token.'
        })

    except Exception as e:
        logger.error(f"Regenerate token error: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/clients/<client_id>/token', methods=['GET'])
def get_client_token(client_id: str):
    """Get client token"""
    try:
        client = execute_query(
            "SELECT client_token, name FROM clients WHERE id = %s",
            (client_id,),
            fetch_one=True
        )

        if not client:
            return jsonify({'error': 'Client not found'}), 404

        return jsonify({
            'token': client['client_token'],
            'client_name': client['name']
        })

    except Exception as e:
        logger.error(f"Get client token error: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/stats', methods=['GET'])
def get_global_stats():
    """Get global statistics"""
    try:
        from core.decision_engine import decision_engine_manager

        stats = execute_query("""
            SELECT
                COUNT(DISTINCT c.id) as total_accounts,
                COUNT(DISTINCT CASE WHEN a.status = 'online' THEN a.id END) as agents_online,
                COUNT(DISTINCT a.id) as agents_total,
                COALESCE(SUM(c.total_savings), 0) as total_savings
            FROM clients c
            LEFT JOIN agents a ON a.client_id = c.id
        """, fetch_one=True)

        switch_stats = execute_query("""
            SELECT
                COUNT(*) as total_switches,
                COUNT(CASE WHEN event_trigger = 'manual' THEN 1 END) as manual_switches,
                COUNT(CASE WHEN event_trigger = 'model' THEN 1 END) as model_switches
            FROM switches
        """, fetch_one=True)

        pool_count = execute_query(
            "SELECT COUNT(*) as count FROM spot_pools WHERE is_active = TRUE",
            fetch_one=True
        )

        backend_health = 'Healthy'
        if not decision_engine_manager.models_loaded:
            backend_health = 'Decision Engine Not Loaded'

        return jsonify({
            'totalAccounts': stats['total_accounts'] or 0,
            'agentsOnline': stats['agents_online'] or 0,
            'agentsTotal': stats['agents_total'] or 0,
            'poolsCovered': pool_count['count'] if pool_count else 0,
            'totalSavings': float(stats['total_savings'] or 0),
            'totalSwitches': switch_stats['total_switches'] if switch_stats else 0,
            'manualSwitches': switch_stats['manual_switches'] if switch_stats else 0,
            'modelSwitches': switch_stats['model_switches'] if switch_stats else 0,
            'backendHealth': backend_health,
            'decisionEngineLoaded': decision_engine_manager.models_loaded,
            'mlModelsLoaded': decision_engine_manager.models_loaded
        })

    except Exception as e:
        logger.error(f"Get global stats error: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/clients', methods=['GET'])
def get_all_clients():
    """Get all clients"""
    try:
        clients = execute_query("""
            SELECT
                c.*,
                COUNT(DISTINCT CASE WHEN a.status = 'online' THEN a.id END) as agents_online,
                COUNT(DISTINCT a.id) as agents_total,
                COUNT(DISTINCT CASE WHEN i.is_active = TRUE THEN i.id END) as instances
            FROM clients c
            LEFT JOIN agents a ON a.client_id = c.id
            LEFT JOIN instances i ON i.client_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """, fetch=True)

        return jsonify([{
            'id': client['id'],
            'name': client['name'],
            'status': 'active' if client['is_active'] else 'inactive',
            'agentsOnline': client['agents_online'] or 0,
            'agentsTotal': client['agents_total'] or 0,
            'instances': client['instances'] or 0,
            'totalSavings': float(client['total_savings'] or 0),
            'lastSync': client['last_sync_at'].isoformat() if client['last_sync_at'] else None
        } for client in clients or []])

    except Exception as e:
        logger.error(f"Get all clients error: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/clients/growth', methods=['GET'])
def get_clients_growth():
    """Get client growth analytics over time"""
    try:
        days = request.args.get('days', 30, type=int)

        # Limit to reasonable range
        days = min(max(days, 1), 365)

        growth_data = execute_query("""
            SELECT
                snapshot_date,
                total_clients,
                new_clients_today,
                active_clients
            FROM clients_daily_snapshot
            WHERE snapshot_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY snapshot_date ASC
        """, (days,), fetch=True)

        return jsonify([{
            'date': g['snapshot_date'].isoformat() if g['snapshot_date'] else None,
            'total': g['total_clients'],
            'new': g['new_clients_today'],
            'active': g['active_clients']
        } for g in growth_data or []])

    except Exception as e:
        logger.error(f"Get clients growth error: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/instances', methods=['GET'])
def get_all_instances_global():
    """Get all instances across all clients (global view)"""
    try:
        # Get filters from query params
        status = request.args.get('status')  # 'active', 'terminated'
        mode = request.args.get('mode')  # 'spot', 'on-demand'
        region = request.args.get('region')

        query = """
            SELECT
                i.*,
                c.name as client_name,
                c.id as client_id,
                a.logical_agent_id,
                a.status as agent_status
            FROM instances i
            LEFT JOIN clients c ON i.client_id = c.id
            LEFT JOIN agents a ON i.id = a.instance_id
            WHERE 1=1
        """
        params = []

        # Filter by instance_status for proper active/terminated separation
        if status:
            if status == 'active':
                # Active space: primary + replica instances only
                query += " AND i.instance_status IN ('running_primary', 'running_replica')"
            elif status == 'terminated':
                # Terminated space: zombie + terminated instances only
                query += " AND i.instance_status IN ('zombie', 'terminated')"

        if mode:
            query += " AND i.current_mode = %s"
            params.append(mode)

        if region:
            query += " AND i.region = %s"
            params.append(region)

        query += " ORDER BY i.created_at DESC LIMIT 500"

        instances = execute_query(query, tuple(params), fetch=True)

        result = [{
            'id': inst['id'],
            'instanceId': inst['id'],  # id IS the instance_id
            'clientId': inst['client_id'],
            'clientName': inst['client_name'],
            'agentId': inst['agent_id'],
            'region': inst['region'],
            'az': inst['az'],
            'instanceType': inst['instance_type'],
            'currentMode': inst['current_mode'],
            'currentPoolId': inst['current_pool_id'],
            'spotPrice': float(inst['spot_price']) if inst['spot_price'] else None,
            'ondemandPrice': float(inst['ondemand_price']) if inst['ondemand_price'] else None,
            'isActive': bool(inst['is_active']),
            'installedAt': inst['installed_at'].isoformat() if inst['installed_at'] else None,
            'createdAt': inst['created_at'].isoformat() if inst['created_at'] else None,
            'logicalAgentId': inst['logical_agent_id'],
            'agentStatus': inst['agent_status']
        } for inst in (instances or [])]

        return jsonify({
            'instances': result,
            'total': len(result),
            'filters': {
                'status': status,
                'mode': mode,
                'region': region
            }
        })

    except Exception as e:
        logger.error(f"Get all instances error: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/agents', methods=['GET'])
def get_all_agents_global():
    """Get all agents across all clients (global view)"""
    try:
        # Get filters from query params
        status = request.args.get('status')  # 'online', 'offline'

        query = """
            SELECT
                a.*,
                c.name as client_name,
                c.id as client_id,
                i.instance_type,
                i.region,
                i.az,
                i.current_mode
            FROM agents a
            LEFT JOIN clients c ON a.client_id = c.id
            LEFT JOIN instances i ON a.instance_id = i.id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND a.status = %s"
            params.append(status)

        query += " ORDER BY a.last_heartbeat_at DESC LIMIT 500"

        agents = execute_query(query, tuple(params), fetch=True)

        result = [{
            'id': agent['id'],
            'logicalAgentId': agent['logical_agent_id'],
            'hostname': agent['hostname'],
            'clientId': agent['client_id'],
            'clientName': agent['client_name'],
            'instanceId': agent['instance_id'],
            'instanceType': agent['instance_type'],
            'region': agent['region'],
            'az': agent['az'],
            'currentMode': agent['current_mode'],
            'currentPoolId': agent['current_pool_id'],
            'status': agent['status'],
            'enabled': bool(agent['enabled']),
            'autoSwitchEnabled': bool(agent['auto_switch_enabled']),
            'version': agent['agent_version'],
            'lastHeartbeatAt': agent['last_heartbeat_at'].isoformat() if agent['last_heartbeat_at'] else None,
            'createdAt': agent['created_at'].isoformat() if agent['created_at'] else None
        } for agent in (agents or [])]

        return jsonify({
            'agents': result,
            'total': len(result),
            'filters': {
                'status': status
            }
        })

    except Exception as e:
        logger.error(f"Get all agents error: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/activity', methods=['GET'])
def get_recent_activity():
    """Get recent system activity"""
    try:
        events = execute_query("""
            SELECT
                event_type as type,
                message as text,
                created_at as time,
                severity
            FROM system_events
            WHERE severity IN ('info', 'warning')
            ORDER BY created_at DESC
            LIMIT 50
        """, fetch=True)

        activity = []
        for i, event in enumerate(events or []):
            event_type_map = {
                'switch_completed': 'switch',
                'agent_registered': 'agent',
                'manual_switch_requested': 'switch',
                'savings_computed': 'event',
                'client_created': 'event',
                'client_deleted': 'event',
                'token_regenerated': 'event'
            }

            activity.append({
                'id': i + 1,
                'type': event_type_map.get(event['type'], 'event'),
                'text': event['text'],
                'time': event['time'].isoformat() if event['time'] else 'unknown'
            })

        return jsonify(activity)

    except Exception as e:
        logger.error(f"Get activity error: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/system-health', methods=['GET'])
def get_system_health():
    """Get system health information"""
    try:
        from core.decision_engine import decision_engine_manager
        from core.database import connection_pool

        db_status = 'Connected'
        try:
            execute_query("SELECT 1", fetch_one=True)
        except:
            db_status = 'Disconnected'

        engine_status = 'Loaded' if decision_engine_manager.models_loaded else 'Not Loaded'

        pool_active = connection_pool._cnx_queue.qsize() if connection_pool else 0

        # Count model files in MODEL_DIR
        model_files_count = 0
        model_files = []
        try:
            if config.MODEL_DIR.exists():
                files = [f for f in config.MODEL_DIR.glob('*') if f.is_file()]
                model_files_count = len(files)
                model_files = [{
                    'name': f.name,
                    'size': f.stat().st_size,
                    'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                } for f in files[:10]]  # Limit to 10 most recent
        except Exception as e:
            logger.warning(f"Could not count model files: {e}")

        # Count decision engine files
        engine_files_count = 0
        engine_files = []
        try:
            if config.DECISION_ENGINE_DIR.exists():
                files = [f for f in config.DECISION_ENGINE_DIR.glob('*.py') if f.is_file()]
                engine_files_count = len(files)
                engine_files = [{
                    'name': f.name,
                    'size': f.stat().st_size,
                    'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                } for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:10]]
        except Exception as e:
            logger.warning(f"Could not count decision engine files: {e}")

        # Get active models from registry
        active_models = []
        try:
            models = execute_query("""
                SELECT model_name, version, is_active, created_at
                FROM model_registry
                WHERE is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 10
            """, fetch=True)
            active_models = [{
                'name': m['model_name'],
                'version': m['version'],
                'active': bool(m['is_active'])
            } for m in (models or [])]
        except Exception as e:
            logger.warning(f"Could not fetch models from registry: {e}")

        return jsonify({
            'apiStatus': 'Healthy',
            'database': db_status,
            'decisionEngine': engine_status,
            'connectionPool': f'{pool_active}/{config.DB_POOL_SIZE}',
            'timestamp': datetime.utcnow().isoformat(),
            'modelStatus': {
                'loaded': decision_engine_manager.models_loaded,
                'name': decision_engine_manager.engine_type or 'None',
                'version': decision_engine_manager.engine_version or 'N/A',
                'filesUploaded': model_files_count,
                'activeModels': active_models,
                'files': model_files
            },
            'decisionEngineStatus': {
                'loaded': decision_engine_manager.models_loaded,
                'type': decision_engine_manager.engine_type or 'None',
                'version': decision_engine_manager.engine_version or 'N/A',
                'filesUploaded': engine_files_count,
                'files': engine_files
            }
        })
    except Exception as e:
        logger.error(f"System health check error: {e}")
        return jsonify({'error': str(e)}), 500
