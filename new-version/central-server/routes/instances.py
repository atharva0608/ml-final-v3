from flask import Blueprint, request, jsonify
import logging
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import success_response, error_response, format_decimal, generate_uuid, create_notification, log_system_event
from core.validation import ForceSwitchSchema
from marshmallow import ValidationError
import json
from datetime import datetime

logger = logging.getLogger(__name__)
instances_bp = Blueprint('instances', __name__)

@instances_bp.route('/api/client/<client_id>/instances', methods=['GET'])
def get_client_instances(client_id: str):
    """Get all instances for client with filtering"""
    status = request.args.get('status', 'all')
    mode = request.args.get('mode', 'all')
    search = request.args.get('search', '')

    try:
        query = "SELECT * FROM instances WHERE client_id = %s"
        params = [client_id]

        # Filter by instance_status for proper active/terminated separation
        if status == 'active':
            # Active space: launching, primary, replica, promoting instances
            query += " AND instance_status IN ('launching', 'running_primary', 'running_replica', 'promoting')"
        elif status == 'terminated':
            # Terminated space: terminating, zombie, terminated instances
            query += " AND instance_status IN ('terminating', 'zombie', 'terminated')"

        if mode != 'all':
            query += " AND current_mode = %s"
            params.append(mode)

        if search:
            query += " AND (id LIKE %s OR instance_type LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])

        query += " ORDER BY created_at DESC"

        instances = execute_query(query, tuple(params), fetch=True)

        return jsonify([{
            'id': inst['id'],
            'type': inst['instance_type'],
            'region': inst['region'],
            'az': inst['az'],
            'mode': inst['current_mode'],
            'poolId': inst['current_pool_id'] or 'n/a',
            'spotPrice': float(inst['spot_price'] or 0),
            'onDemandPrice': float(inst['ondemand_price'] or 0),
            'isActive': inst['is_active'],
            'instanceStatus': inst.get('instance_status', 'running_primary'),
            'isPrimary': inst.get('is_primary', True),
            'lastSwitch': inst['last_switch_at'].isoformat() if inst['last_switch_at'] else None
        } for inst in instances or []])

    except Exception as e:
        logger.error(f"Get instances error: {e}")
        return jsonify({'error': str(e)}), 500

@instances_bp.route('/api/client/instances/<instance_id>/pricing', methods=['GET'])
def get_instance_pricing(instance_id: str):
    """Get pricing details for instance with current mode and pool info"""
    try:
        # Get instance details including current state
        instance = execute_query("""
            SELECT i.instance_type, i.region, i.ondemand_price, i.current_pool_id, i.current_mode, i.client_id
            FROM instances i
            WHERE i.id = %s
        """, (instance_id,), fetch_one=True)

        if not instance:
            return jsonify({'error': 'Instance not found'}), 404

        # Get all available pools for this instance type with latest prices
        pools = execute_query("""
            SELECT
                sp.id as pool_id,
                sp.pool_name,
                sp.az,
                sps.price as price,
                sps.captured_at as captured_at
            FROM spot_pools sp
            LEFT JOIN (
                SELECT pool_id, price, captured_at,
                       ROW_NUMBER() OVER (PARTITION BY pool_id ORDER BY captured_at DESC) as rn
                FROM spot_price_snapshots
                WHERE captured_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            ) sps ON sps.pool_id = sp.id AND sps.rn = 1
            WHERE sp.instance_type = %s AND sp.region = %s
            ORDER BY COALESCE(sps.price, 999999) ASC
        """, (instance['instance_type'], instance['region']), fetch=True)

        ondemand_price = float(instance['ondemand_price'] or 0)

        # Get current pool details
        current_pool = None
        if instance['current_pool_id']:
            current_pool_data = execute_query("""
                SELECT id, pool_name, az FROM spot_pools WHERE id = %s
            """, (instance['current_pool_id'],), fetch_one=True)
            if current_pool_data:
                current_pool = {
                    'id': current_pool_data['id'],
                    'name': current_pool_data['pool_name'],
                    'az': current_pool_data['az']
                }

        return jsonify({
            'currentMode': instance['current_mode'] or 'ondemand',
            'currentPool': current_pool,
            'onDemand': {
                'name': 'On-Demand',
                'price': ondemand_price
            },
            'pools': [{
                'id': pool['pool_id'],
                'name': pool['pool_name'] or f"Pool {pool['pool_id']}",
                'az': pool['az'],
                'price': float(pool['price']) if pool['price'] else 0,
                'savings': ((ondemand_price - float(pool['price'])) / ondemand_price * 100) if (ondemand_price > 0 and pool['price']) else 0
            } for pool in pools or []]
        })

    except Exception as e:
        logger.error(f"Get instance pricing error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@instances_bp.route('/api/client/instances/<instance_id>/metrics', methods=['GET'])
def get_instance_metrics(instance_id: str):
    """Get comprehensive instance metrics"""
    try:
        metrics = execute_query("""
            SELECT
                i.id,
                i.instance_type,
                i.current_mode,
                i.current_pool_id,
                i.spot_price,
                i.ondemand_price,
                i.baseline_ondemand_price,
                TIMESTAMPDIFF(HOUR, i.installed_at, NOW()) as uptime_hours,
                TIMESTAMPDIFF(HOUR, i.last_switch_at, NOW()) as hours_since_last_switch,
                (SELECT COUNT(*) FROM switches WHERE new_instance_id = i.id) as total_switches,
                (SELECT COUNT(*) FROM switches
                 WHERE new_instance_id = i.id
                 AND initiated_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)) as switches_last_7_days,
                (SELECT COUNT(*) FROM switches
                 WHERE new_instance_id = i.id
                 AND initiated_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)) as switches_last_30_days,
                (SELECT SUM(savings_impact * 24) FROM switches
                 WHERE new_instance_id = i.id
                 AND initiated_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)) as savings_last_30_days,
                (SELECT SUM(savings_impact * 24) FROM switches
                 WHERE new_instance_id = i.id) as total_savings
            FROM instances i
            WHERE i.id = %s
        """, (instance_id,), fetch_one=True)

        if not metrics:
            return jsonify({'error': 'Instance not found'}), 404

        return jsonify({
            'id': metrics['id'],
            'instanceType': metrics['instance_type'],
            'currentMode': metrics['current_mode'],
            'currentPoolId': metrics['current_pool_id'],
            'spotPrice': float(metrics['spot_price'] or 0),
            'onDemandPrice': float(metrics['ondemand_price'] or 0),
            'baselineOnDemandPrice': float(metrics['baseline_ondemand_price'] or 0),
            'uptimeHours': metrics['uptime_hours'] or 0,
            'hoursSinceLastSwitch': metrics['hours_since_last_switch'] or 0,
            'totalSwitches': metrics['total_switches'] or 0,
            'switchesLast7Days': metrics['switches_last_7_days'] or 0,
            'switchesLast30Days': metrics['switches_last_30_days'] or 0,
            'savingsLast30Days': float(metrics['savings_last_30_days'] or 0),
            'totalSavings': float(metrics['total_savings'] or 0)
        })

    except Exception as e:
        logger.error(f"Get instance metrics error: {e}")
        return jsonify({'error': str(e)}), 500

@instances_bp.route('/api/client/instances/<instance_id>/price-history', methods=['GET'])
def get_instance_price_history(instance_id: str):
    """Get historical pricing data for all pools (for multi-line chart)"""
    try:
        days = request.args.get('days', 7, type=int)
        interval = request.args.get('interval', 'hour')  # 'hour' or 'day'

        # Limit to reasonable range
        days = min(max(days, 1), 90)

        # Get instance info
        instance = execute_query("""
            SELECT i.id, i.instance_type, i.region, i.ondemand_price
            FROM instances i
            WHERE i.id = %s
        """, (instance_id,), fetch_one=True)

        if not instance:
            return jsonify({'error': 'Instance not found'}), 404

        # Get all pools for this instance type
        pools = execute_query("""
            SELECT id, pool_name, az
            FROM spot_pools
            WHERE instance_type = %s AND region = %s
        """, (instance['instance_type'], instance['region']), fetch=True)

        if not pools:
            return jsonify([])

        # Get pricing data for all pools
        time_format = '%%Y-%%m-%%d %%H:00' if interval == 'hour' else '%%Y-%%m-%%d'

        # Build IN clause with proper parameters
        pool_ids = [p['id'] for p in pools]
        placeholders = ','.join(['%s'] * len(pool_ids))

        # Query to get pricing for all pools from real-time snapshots
        query = f"""
            SELECT
                DATE_FORMAT(sps.captured_at, %s) as time,
                sps.pool_id,
                AVG(sps.price) as price
            FROM spot_price_snapshots sps
            WHERE sps.pool_id IN ({placeholders})
              AND sps.captured_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY DATE_FORMAT(sps.captured_at, %s), sps.pool_id
            ORDER BY time ASC, sps.pool_id
        """

        params = [time_format] + pool_ids + [days, time_format]
        price_data = execute_query(query, tuple(params), fetch=True)

        # Get unique timestamps
        timestamps = sorted(set(row['time'] for row in (price_data or [])))

        # Build result with each timestamp having prices for all pools
        pool_map = {p['id']: {'name': p['pool_name'], 'az': p['az']} for p in pools}
        price_map = {}
        for row in (price_data or []):
            key = str(row['time'])
            if key not in price_map:
                price_map[key] = {}
            price_map[key][row['pool_id']] = float(row['price'])

        # Build final result
        result = []
        ondemand_price = float(instance['ondemand_price'] or 0)

        for timestamp in timestamps:
            data_point = {
                'time': timestamp,
                'onDemand': ondemand_price
            }
            # Add each pool's price
            for pool in pools:
                pool_id = pool['id']
                pool_key = f"pool_{pool_id}"
                data_point[pool_key] = price_map.get(timestamp, {}).get(pool_id, None)
            result.append(data_point)

        # Also return pool metadata for the frontend to know which lines to draw
        pool_metadata = [{
            'id': p['id'],
            'name': p['pool_name'] or f"Pool {p['id']}",
            'az': p['az'],
            'key': f"pool_{p['id']}"
        } for p in pools]

        return jsonify({
            'data': result,
            'pools': pool_metadata,
            'onDemandPrice': ondemand_price
        })

    except Exception as e:
        logger.error(f"Get price history error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@instances_bp.route('/api/client/instances/<instance_id>/available-options', methods=['GET'])
def get_instance_available_options(instance_id: str):
    """Get available pools and instance types for switching"""
    try:
        # Get current instance information from agents table (primary source)
        agent = execute_query("""
            SELECT instance_type, region, az FROM agents WHERE instance_id = %s
        """, (instance_id,), fetch_one=True)

        # Fallback: Check instances table if agent hasn't sent heartbeat yet
        if not agent:
            agent = execute_query("""
                SELECT instance_type, region, az FROM instances WHERE id = %s
            """, (instance_id,), fetch_one=True)

        if not agent:
            return jsonify({'error': 'Instance not found'}), 404

        current_type = agent['instance_type']
        region = agent['region']

        # Get available pools for current instance type
        pools = execute_query("""
            SELECT
                sp.id as pool_id,
                sp.az,
                sp.instance_type,
                spr.price as current_price
            FROM spot_pools sp
            LEFT JOIN (
                SELECT
                    pool_id,
                    price,
                    ROW_NUMBER() OVER (PARTITION BY pool_id ORDER BY captured_at DESC) as rn
                FROM spot_price_snapshots
            ) spr ON spr.pool_id = sp.id AND spr.rn = 1
            WHERE sp.instance_type = %s
              AND sp.region = %s
              AND sp.is_active = TRUE
            ORDER BY spr.price ASC
        """, (current_type, region), fetch=True)

        # Get instance types in same family (e.g., t3.medium -> t3.*)
        base_family = current_type.split('.')[0] if current_type else ''
        instance_types = execute_query("""
            SELECT DISTINCT instance_type
            FROM spot_pools
            WHERE region = %s
              AND instance_type LIKE %s
              AND is_active = TRUE
            ORDER BY instance_type
        """, (region, f"{base_family}.%"), fetch=True) if base_family else []

        return jsonify({
            'currentType': current_type,
            'currentRegion': region,
            'currentAz': agent.get('az'),
            'availablePools': [{
                'id': p['pool_id'],
                'az': p['az'],
                'instanceType': p['instance_type'],
                'price': float(p['current_price']) if p.get('current_price') else None
            } for p in pools or []],
            'availableTypes': [t['instance_type'] for t in instance_types or []]
        })

    except Exception as e:
        logger.error(f"Get available options error: {e}")
        return jsonify({'error': str(e)}), 500

@instances_bp.route('/api/client/instances/<instance_id>/force-switch', methods=['POST'])
def force_instance_switch(instance_id: str):
    """Manually force instance switch"""
    data = request.json or {}

    schema = ForceSwitchSchema()
    try:
        validated_data = schema.load(data)
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400

    try:
        instance = execute_query("""
            SELECT agent_id, client_id FROM instances WHERE id = %s
        """, (instance_id,), fetch_one=True)

        if not instance:
            # Try to find agent by instance_id
            agent = execute_query("""
                SELECT id, client_id FROM agents WHERE instance_id = %s
            """, (instance_id,), fetch_one=True)

            if not agent:
                return jsonify({'error': 'Instance or agent not found'}), 404

            instance = {'agent_id': agent['id'], 'client_id': agent['client_id']}

        if not instance.get('agent_id'):
            return jsonify({'error': 'No agent assigned to instance'}), 404

        target_mode = validated_data['target']
        target_pool_id = validated_data.get('pool_id')
        new_instance_type = validated_data.get('new_instance_type')

        # Get agent's auto-terminate configuration
        agent_config = execute_query("""
            SELECT auto_terminate_enabled, terminate_wait_seconds
            FROM agents
            WHERE id = %s
        """, (instance['agent_id'],), fetch_one=True)

        # Determine terminate_wait_seconds based on auto_terminate setting
        if agent_config and agent_config['auto_terminate_enabled']:
            terminate_wait = agent_config['terminate_wait_seconds'] or 300
        else:
            terminate_wait = 0  # Signal: DO NOT terminate old instance

        # Build metadata for logging
        metadata = {
            'target': target_mode,
            'pool_id': target_pool_id
        }
        if new_instance_type:
            metadata['new_instance_type'] = new_instance_type
            # Note: Instance type changes require agent-side support
            logger.info(f"Instance type change requested: {new_instance_type}")

        # Insert pending command with manual priority (75) and terminate_wait_seconds
        command_id = generate_uuid()
        execute_query("""
            INSERT INTO commands
            (id, client_id, agent_id, instance_id, command_type, target_mode, target_pool_id, priority, terminate_wait_seconds, status, created_by)
            VALUES (%s, %s, %s, %s, 'switch', %s, %s, 75, %s, 'pending', 'manual')
        """, (
            command_id,
            instance['client_id'],
            instance['agent_id'],
            instance_id,
            target_mode if target_mode != 'pool' else 'spot',
            target_pool_id,
            terminate_wait
        ))

        notification_msg = f"Manual switch queued for {instance_id}"
        if new_instance_type:
            notification_msg += f" (type: {new_instance_type})"

        create_notification(
            notification_msg,
            'warning',
            instance['client_id']
        )

        log_system_event('manual_switch_requested', 'info',
                        f"Manual switch requested for {instance_id} to {target_mode}",
                        instance['client_id'], instance['agent_id'], instance_id,
                        metadata=metadata)

        return jsonify({
            'success': True,
            'command_id': command_id,
            'message': 'Switch command queued. Agent will execute on next check.'
        })

    except Exception as e:
        logger.error(f"Force switch error: {e}")
        return jsonify({'error': str(e)}), 500

@instances_bp.route('/api/client/instances/<instance_id>/logs', methods=['GET'])
@require_client_auth
def get_instance_logs(instance_id: str):
    """
    Get lifecycle event logs for an instance.

    Query Parameters:
        limit: Maximum number of logs to return (default: 100)

    Returns chronological event logs for debugging and monitoring.
    """
    try:
        limit = int(request.args.get('limit', 100))
        limit = min(limit, 1000)  # Cap at 1000

        # Try to get from instance_event_logs table if it exists
        logs = execute_query("""
            SELECT
                created_at as timestamp,
                event_type,
                message,
                severity,
                metadata
            FROM instance_event_logs
            WHERE instance_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (instance_id, limit), fetch=True)

        if logs:
            return jsonify([{
                'timestamp': log['timestamp'].isoformat() if log['timestamp'] else None,
                'event_type': log['event_type'],
                'message': log['message'],
                'severity': log['severity'],
                'metadata': json.loads(log['metadata']) if log.get('metadata') else {}
            } for log in logs])

        # Fallback: Generate logs from switches table
        switches = execute_query("""
            SELECT
                initiated_at,
                old_instance_id,
                new_instance_id,
                from_pool,
                to_pool,
                trigger,
                downtime_seconds,
                savings_impact
            FROM switches
            WHERE old_instance_id = %s OR new_instance_id = %s
            ORDER BY initiated_at DESC
            LIMIT %s
        """, (instance_id, instance_id, limit), fetch=True)

        fallback_logs = []
        for sw in (switches or []):
            fallback_logs.append({
                'timestamp': sw['initiated_at'].isoformat() if sw['initiated_at'] else None,
                'event_type': 'switch_initiated' if sw['old_instance_id'] == instance_id else 'switch_target',
                'message': f"Switch initiated to pool {sw['to_pool']}" if sw['old_instance_id'] == instance_id else f"Became target of switch from {sw['from_pool']}",
                'severity': 'info',
                'metadata': {
                    'from_pool': sw['from_pool'],
                    'to_pool': sw['to_pool'],
                    'trigger': sw['trigger'],
                    'downtime_seconds': sw['downtime_seconds'],
                    'savings_impact': float(sw['savings_impact'] or 0.0)
                }
            })

        return jsonify(fallback_logs)

    except Exception as e:
        logger.error(f"Get instance logs error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@instances_bp.route('/api/client/instances/<instance_id>/pool-volatility', methods=['GET'])
@require_client_auth
def get_pool_volatility(instance_id: str):
    """
    Get volatility/stability indicators for pools.

    Returns volatility scores and interruption rates for current and alternative pools.
    """
    try:
        # Get current instance info
        instance = execute_query("""
            SELECT current_pool_id, spot_price, instance_type, region
            FROM instances
            WHERE id = %s
        """, (instance_id,), fetch_one=True)

        if not instance:
            return jsonify({'error': 'Instance not found'}), 404

        current_pool = instance['current_pool_id']

        # Calculate volatility for current pool (std dev of prices over 24h)
        current_volatility = execute_query("""
            SELECT
                pool_id,
                AVG(spot_price) as avg_price,
                STDDEV(spot_price) as price_stddev,
                COUNT(*) as data_points
            FROM spot_pricing_history
            WHERE pool_id = %s
            AND observed_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            GROUP BY pool_id
        """, (current_pool,), fetch_one=True)

        # Get alternative pools (same instance type, different AZ)
        alternative_pools = execute_query("""
            SELECT
                pool_id,
                AVG(spot_price) as avg_price,
                STDDEV(spot_price) as price_stddev,
                COUNT(*) as data_points
            FROM spot_pricing_history
            WHERE instance_type = %s
            AND region = %s
            AND pool_id != %s
            AND observed_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            GROUP BY pool_id
            ORDER BY avg_price ASC
            LIMIT 5
        """, (instance['instance_type'], instance['region'], current_pool), fetch=True)

        def calculate_volatility_category(stddev, avg):
            if not stddev or not avg:
                return 'unknown'
            coefficient = stddev / avg if avg > 0 else 0
            if coefficient < 0.05:
                return 'very_low'
            elif coefficient < 0.10:
                return 'low'
            elif coefficient < 0.20:
                return 'medium'
            else:
                return 'high'

        # Format response
        current_data = {
            'pool_id': current_pool,
            'current_price': float(instance['spot_price'] or 0.0),
            'volatility_score': float(current_volatility['price_stddev'] or 0.0) if current_volatility else 0.0,
            'volatility_category': calculate_volatility_category(
                current_volatility['price_stddev'] if current_volatility else None,
                current_volatility['avg_price'] if current_volatility else None
            ),
            'interruption_rate_24h': 0.003,  # Placeholder - would come from interruption_events table
            'price_stability_7d': 'stable'  # Placeholder - would require 7-day analysis
        }

        alternative_data = [{
            'pool_id': pool['pool_id'],
            'current_price': float(pool['avg_price'] or 0.0),
            'volatility_score': float(pool['price_stddev'] or 0.0),
            'volatility_category': calculate_volatility_category(pool['price_stddev'], pool['avg_price']),
            'interruption_rate_24h': 0.001,  # Placeholder
            'price_stability_7d': 'very_stable',  # Placeholder
            'recommendation': 'best' if pool['avg_price'] < instance['spot_price'] else None
        } for pool in (alternative_pools or [])]

        return jsonify({
            'current_pool': current_data,
            'alternative_pools': alternative_data
        })

    except Exception as e:
        logger.error(f"Get pool volatility error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@instances_bp.route('/api/client/instances/<instance_id>/simulate-switch', methods=['POST'])
@require_client_auth
def simulate_switch(instance_id: str):
    """
    Simulate a switch to see expected savings and downtime.

    Request Body:
        {
            "target_pool": "us-east-1b-pool-3",
            "target_type": "spot"
        }

    Returns estimated impact without actually performing the switch.
    """
    try:
        data = request.json
        target_pool = data.get('target_pool')
        target_type = data.get('target_type', 'spot')

        # Get current instance
        instance = execute_query("""
            SELECT
                id,
                current_pool_id,
                spot_price as current_price,
                ondemand_price,
                instance_type
            FROM instances
            WHERE id = %s
        """, (instance_id,), fetch_one=True)

        if not instance:
            return jsonify({'error': 'Instance not found'}), 404

        # Get target pool price
        target_price = None
        if target_type == 'ondemand':
            target_price = instance['ondemand_price']
        else:
            target_pool_data = execute_query("""
                SELECT AVG(spot_price) as avg_price
                FROM spot_pricing_history
                WHERE pool_id = %s
                AND observed_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """, (target_pool,), fetch_one=True)
            target_price = target_pool_data['avg_price'] if target_pool_data else instance['current_price']

        # Calculate savings
        current_price = float(instance['current_price'] or 0.0)
        target_price = float(target_price or 0.0)
        hourly_savings = current_price - target_price
        daily_savings = hourly_savings * 24
        monthly_savings = daily_savings * 30

        # Estimate downtime (based on historical averages)
        avg_downtime = execute_query("""
            SELECT AVG(downtime_seconds) as avg_downtime
            FROM switches
            WHERE trigger = 'manual'
        """, fetch_one=True)
        estimated_downtime = int(avg_downtime['avg_downtime'] or 12) if avg_downtime else 12

        # Calculate confidence and risk
        confidence = 0.87 if hourly_savings > 0 else 0.50
        volatility_risk = 'low' if target_type == 'ondemand' else 'medium'

        # Determine recommendation
        if hourly_savings > 0.002:
            recommendation = 'strongly_recommended'
        elif hourly_savings > 0:
            recommendation = 'recommended'
        elif hourly_savings == 0:
            recommendation = 'neutral'
        else:
            recommendation = 'not_recommended'

        simulation = {
            'current_price': current_price,
            'target_price': target_price,
            'hourly_savings': round(hourly_savings, 4),
            'daily_savings': round(daily_savings, 4),
            'monthly_savings': round(monthly_savings, 2),
            'estimated_downtime_seconds': estimated_downtime,
            'confidence': confidence,
            'volatility_risk': volatility_risk,
            'interruption_probability_24h': 0.002 if target_type == 'spot' else 0.0,
            'recommendation': recommendation
        }

        return jsonify({'simulation': simulation})

    except Exception as e:
        logger.error(f"Simulate switch error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ============================================================================
# REAL-TIME INSTANCE OPERATIONS (LAUNCHING/TERMINATING)
# ============================================================================

@instances_bp.route('/api/client/instances/launch', methods=['POST'])
@require_client_auth
def launch_instance():
    """Launch new instance with real-time state tracking"""
    data = request.json or {}

    try:
        agent_id = data.get('agent_id')
        instance_type = data.get('instance_type')
        target_mode = data.get('target_mode', 'spot')  # spot or ondemand
        target_pool_id = data.get('target_pool_id')
        az = data.get('az')
        role_hint = data.get('role_hint', 'replica')  # replica or primary

        if not agent_id:
            return jsonify({'error': 'agent_id required'}), 400

        # Verify agent belongs to client
        agent = execute_query("""
            SELECT id, client_id, region
            FROM agents
            WHERE id = %s AND client_id = %s
        """, (agent_id, request.client_id), fetch_one=True)

        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        # Generate unique IDs
        instance_id = f"i-pending-{generate_uuid()[:8]}"  # Temporary ID until AWS confirms
        command_id = generate_uuid()
        request_id = generate_uuid()

        # Create instance record in LAUNCHING state
        execute_query("""
            INSERT INTO instances
            (id, client_id, agent_id, instance_type, region, az, current_mode, current_pool_id,
             instance_status, is_primary, is_active, launch_requested_at, installed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'launching', %s, TRUE, NOW(), NOW())
        """, (
            instance_id,
            request.client_id,
            agent_id,
            instance_type or 't3.medium',
            agent['region'],
            az or '',
            target_mode,
            target_pool_id or '',
            role_hint == 'primary'
        ))

        # Create LAUNCH_INSTANCE command for immediate execution
        execute_query("""
            INSERT INTO commands
            (id, client_id, agent_id, instance_id, command_type, target_mode, target_pool_id,
             request_id, priority, status, created_by, metadata)
            VALUES (%s, %s, %s, %s, 'LAUNCH_INSTANCE', %s, %s, %s, 100, 'pending', 'manual', %s)
        """, (
            command_id,
            request.client_id,
            agent_id,
            instance_id,
            target_mode,
            target_pool_id or '',
            request_id,
            json.dumps({
                'instance_type': instance_type or 't3.medium',
                'az': az or '',
                'role_hint': role_hint,
                'immediate': True  # Flag for immediate execution
            })
        ))

        # Log event
        log_system_event('instance_launch_requested', 'info',
                        f"Launch requested for new instance (type: {instance_type}, mode: {target_mode})",
                        request.client_id, agent_id, instance_id,
                        metadata={'command_id': command_id, 'role': role_hint})

        # Create notification
        create_notification(
            f"Launching new {target_mode} instance ({instance_type})",
            'info',
            request.client_id
        )

        return jsonify({
            'success': True,
            'instance_id': instance_id,
            'command_id': command_id,
            'request_id': request_id,
            'status': 'launching',
            'message': 'Instance launch initiated. Agent will execute immediately.'
        }), 201

    except Exception as e:
        logger.error(f"Launch instance error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instances_bp.route('/api/client/instances/<instance_id>/terminate', methods=['POST'])
@require_client_auth
def terminate_instance(instance_id: str):
    """Terminate instance with real-time state tracking"""
    data = request.json or {}

    try:
        # Get instance
        instance = execute_query("""
            SELECT id, client_id, agent_id, instance_status, version
            FROM instances
            WHERE id = %s
        """, (instance_id,), fetch_one=True)

        if not instance:
            return jsonify({'error': 'Instance not found'}), 404

        # Verify client owns instance
        if instance['client_id'] != request.client_id:
            return jsonify({'error': 'Unauthorized'}), 403

        # Check if already terminating/terminated
        if instance['instance_status'] in ('terminating', 'terminated'):
            return jsonify({
                'success': True,
                'instance_id': instance_id,
                'status': instance['instance_status'],
                'message': f"Instance already {instance['instance_status']}"
            })

        # Update instance to TERMINATING state with optimistic locking
        rows_affected = execute_query("""
            UPDATE instances
            SET instance_status = 'terminating',
                termination_requested_at = NOW(),
                is_active = FALSE
            WHERE id = %s AND version = %s
        """, (instance_id, instance['version']))

        if not rows_affected or rows_affected == 0:
            return jsonify({'error': 'Instance state changed, please retry'}), 409

        # Create TERMINATE_INSTANCE command for immediate execution
        command_id = generate_uuid()
        request_id = generate_uuid()

        execute_query("""
            INSERT INTO commands
            (id, client_id, agent_id, instance_id, command_type, request_id,
             priority, status, created_by, metadata)
            VALUES (%s, %s, %s, %s, 'TERMINATE_INSTANCE', %s, 100, 'pending', 'manual', %s)
        """, (
            command_id,
            request.client_id,
            instance['agent_id'],
            instance_id,
            request_id,
            json.dumps({'immediate': True})
        ))

        # Log event
        log_system_event('instance_termination_requested', 'info',
                        f"Termination requested for instance {instance_id}",
                        request.client_id, instance['agent_id'], instance_id,
                        metadata={'command_id': command_id})

        # Create notification
        create_notification(
            f"Terminating instance {instance_id}",
            'warning',
            request.client_id
        )

        return jsonify({
            'success': True,
            'instance_id': instance_id,
            'command_id': command_id,
            'request_id': request_id,
            'status': 'terminating',
            'message': 'Instance termination initiated. Agent will execute immediately.'
        })

    except Exception as e:
        logger.error(f"Terminate instance error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instances_bp.route('/api/agents/<agent_id>/instance-launched', methods=['POST'])
@require_client_auth
def instance_launched_confirmation(agent_id: str):
    """Handle LAUNCH_CONFIRMED from agent after AWS confirms instance is running"""
    data = request.json or {}

    try:
        temp_instance_id = data.get('temp_instance_id')  # The temporary ID we assigned
        real_instance_id = data.get('instance_id')  # Real AWS instance ID
        instance_type = data.get('instance_type')
        az = data.get('az')
        request_id = data.get('request_id')

        if not temp_instance_id or not real_instance_id:
            return jsonify({'error': 'temp_instance_id and instance_id required'}), 400

        # Check idempotency
        existing = execute_query("""
            SELECT id FROM instances WHERE id = %s
        """, (real_instance_id,), fetch_one=True)

        if existing:
            logger.info(f"Instance {real_instance_id} already confirmed (idempotent)")
            return jsonify({'success': True, 'message': 'Already confirmed'})

        # Update instance: replace temp ID with real ID, move to running_replica/running_primary
        instance = execute_query("""
            SELECT instance_status, is_primary, launch_requested_at
            FROM instances
            WHERE id = %s AND agent_id = %s
        """, (temp_instance_id, agent_id), fetch_one=True)

        if not instance:
            return jsonify({'error': 'Temporary instance not found'}), 404

        # Determine final status
        final_status = 'running_primary' if instance['is_primary'] else 'running_replica'

        # Calculate launch duration
        launch_duration = None
        if instance['launch_requested_at']:
            from datetime import datetime
            launch_duration = int((datetime.utcnow() - instance['launch_requested_at']).total_seconds())

        # Update with real instance ID
        execute_query("""
            UPDATE instances
            SET id = %s,
                instance_status = %s,
                instance_type = COALESCE(%s, instance_type),
                az = COALESCE(%s, az),
                launch_confirmed_at = NOW(),
                launch_duration_seconds = %s
            WHERE id = %s AND agent_id = %s
        """, (
            real_instance_id,
            final_status,
            instance_type,
            az,
            launch_duration,
            temp_instance_id,
            agent_id
        ))

        # Log event
        log_system_event('instance_launch_confirmed', 'info',
                        f"Instance {real_instance_id} confirmed running (duration: {launch_duration}s)",
                        request.client_id, agent_id, real_instance_id,
                        metadata={'temp_id': temp_instance_id, 'launch_duration': launch_duration})

        # Create notification
        create_notification(
            f"Instance {real_instance_id} is now running",
            'success',
            request.client_id
        )

        return jsonify({
            'success': True,
            'instance_id': real_instance_id,
            'status': final_status,
            'launch_duration_seconds': launch_duration
        })

    except Exception as e:
        logger.error(f"Launch confirmation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instances_bp.route('/api/agents/<agent_id>/instance-terminated', methods=['POST'])
@require_client_auth
def instance_terminated_confirmation(agent_id: str):
    """Handle TERMINATE_CONFIRMED from agent after AWS confirms instance is terminated"""
    data = request.json or {}

    try:
        instance_id = data.get('instance_id')
        request_id = data.get('request_id')

        if not instance_id:
            return jsonify({'error': 'instance_id required'}), 400

        # Get instance
        instance = execute_query("""
            SELECT id, instance_status, termination_requested_at, version
            FROM instances
            WHERE id = %s AND agent_id = %s
        """, (instance_id, agent_id), fetch_one=True)

        if not instance:
            return jsonify({'error': 'Instance not found'}), 404

        # Check if already terminated (idempotency)
        if instance['instance_status'] == 'terminated':
            logger.info(f"Instance {instance_id} already terminated (idempotent)")
            return jsonify({'success': True, 'message': 'Already terminated'})

        # Calculate termination duration
        termination_duration = None
        if instance['termination_requested_at']:
            from datetime import datetime
            termination_duration = int((datetime.utcnow() - instance['termination_requested_at']).total_seconds())

        # Update to TERMINATED state with optimistic locking
        rows_affected = execute_query("""
            UPDATE instances
            SET instance_status = 'terminated',
                termination_confirmed_at = NOW(),
                terminated_at = NOW(),
                termination_duration_seconds = %s,
                is_active = FALSE
            WHERE id = %s AND agent_id = %s AND version = %s
        """, (
            termination_duration,
            instance_id,
            agent_id,
            instance['version']
        ))

        if not rows_affected or rows_affected == 0:
            return jsonify({'error': 'Instance state changed, please retry'}), 409

        # Log event
        log_system_event('instance_termination_confirmed', 'info',
                        f"Instance {instance_id} confirmed terminated (duration: {termination_duration}s)",
                        request.client_id, agent_id, instance_id,
                        metadata={'termination_duration': termination_duration})

        # Create notification
        create_notification(
            f"Instance {instance_id} has been terminated",
            'info',
            request.client_id
        )

        return jsonify({
            'success': True,
            'instance_id': instance_id,
            'status': 'terminated',
            'termination_duration_seconds': termination_duration
        })

    except Exception as e:
        logger.error(f"Termination confirmation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
