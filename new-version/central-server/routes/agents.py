from flask import Blueprint, request, jsonify
import logging
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import success_response, error_response, format_decimal, generate_uuid, create_notification, log_system_event
from core.validation import AgentRegistrationSchema
from marshmallow import ValidationError
import json
from datetime import datetime

logger = logging.getLogger(__name__)
agents_bp = Blueprint('agents', __name__)

@agents_bp.route('/api/agents/register', methods=['POST'])
@require_client_auth
def register_agent():
    """Register new agent with validation"""
    data = request.json

    # Log registration attempt for debugging
    logger.info(f"Agent registration attempt from client {request.client_id}")
    logger.debug(f"Registration data: {data}")

    schema = AgentRegistrationSchema()
    try:
        validated_data = schema.load(data)
    except ValidationError as e:
        logger.warning(f"Agent registration validation failed: {e.messages}")
        log_system_event('validation_error', 'warning',
                        f"Agent registration validation failed: {e.messages}",
                        request.client_id)
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400

    try:
        logical_agent_id = validated_data['logical_agent_id']

        # Log successful validation
        logger.info(f"Agent registration validated: logical_id={logical_agent_id}, instance_id={validated_data['instance_id']}, mode={validated_data['mode']}")

        # Check if agent exists
        existing = execute_query(
            "SELECT id FROM agents WHERE logical_agent_id = %s AND client_id = %s",
            (logical_agent_id, request.client_id),
            fetch_one=True
        )

        if existing:
            agent_id = existing['id']
            logger.info(f"Updating existing agent: agent_id={agent_id}, logical_id={logical_agent_id}")

            # Check if this instance is a zombie or terminated - if so, don't let it update the agent
            instance_status_check = execute_query("""
                SELECT instance_status, is_primary
                FROM instances
                WHERE id = %s
            """, (validated_data['instance_id'],), fetch_one=True)

            # If this is a zombie or terminated instance, or not primary, reject the registration update
            if instance_status_check:
                status = instance_status_check.get('instance_status')
                is_primary = instance_status_check.get('is_primary')

                if status in ('zombie', 'terminated') or not is_primary:
                    logger.warning(f"Rejecting registration from non-primary/zombie instance {validated_data['instance_id']} (status={status}, is_primary={is_primary})")
                    # Return success but don't update agent - zombie should not become primary again
                    return jsonify({
                        'agent_id': agent_id,
                        'client_id': request.client_id,
                        'message': 'Instance is not primary, registration ignored',
                        'config': {
                            'enabled': False,
                            'auto_switch_enabled': False,
                            'auto_terminate_enabled': False,
                            'terminate_wait_seconds': 0,
                            'replica_enabled': False,
                            'replica_count': 0,
                            'min_savings_percent': 0,
                            'risk_threshold': 0,
                            'max_switches_per_week': 0,
                            'min_pool_duration_hours': 0
                        }
                    })

            # Update existing agent (only if instance is primary or doesn't exist in instances table yet)
            execute_query("""
                UPDATE agents
                SET status = 'online',
                    hostname = %s,
                    instance_id = %s,
                    instance_type = %s,
                    region = %s,
                    az = %s,
                    ami_id = %s,
                    current_mode = %s,
                    current_pool_id = %s,
                    agent_version = %s,
                    private_ip = %s,
                    public_ip = %s,
                    last_heartbeat_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (
                validated_data.get('hostname'),
                validated_data['instance_id'],
                validated_data['instance_type'],
                validated_data['region'],
                validated_data['az'],
                validated_data.get('ami_id'),
                validated_data['mode'],
                f"{validated_data['instance_type']}.{validated_data['az']}" if validated_data['mode'] == 'spot' else None,
                validated_data.get('agent_version'),
                validated_data.get('private_ip'),
                validated_data.get('public_ip'),
                agent_id
            ))
        else:
            # Insert new agent
            agent_id = generate_uuid()
            logger.info(f"Creating new agent: agent_id={agent_id}, logical_id={logical_agent_id}")
            execute_query("""
                INSERT INTO agents
                (id, client_id, logical_agent_id, hostname, instance_id, instance_type,
                 region, az, ami_id, current_mode, current_pool_id, agent_version,
                 private_ip, public_ip, status, last_heartbeat_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'online', NOW())
            """, (
                agent_id,
                request.client_id,
                logical_agent_id,
                validated_data.get('hostname'),
                validated_data['instance_id'],
                validated_data['instance_type'],
                validated_data['region'],
                validated_data['az'],
                validated_data.get('ami_id'),
                validated_data['mode'],
                f"{validated_data['instance_type']}.{validated_data['az']}" if validated_data['mode'] == 'spot' else None,
                validated_data.get('agent_version'),
                validated_data.get('private_ip'),
                validated_data.get('public_ip')
            ))

            # Create default config
            execute_query("""
                INSERT INTO agent_configs (agent_id)
                VALUES (%s)
            """, (agent_id,))

            create_notification(
                f"New agent registered: {logical_agent_id}",
                'info',
                request.client_id
            )

        # Handle instance registration
        instance_exists = execute_query(
            "SELECT id FROM instances WHERE id = %s",
            (validated_data['instance_id'],),
            fetch_one=True
        )

        if not instance_exists:
            # Get latest on-demand price
            latest_od_price = execute_query("""
                SELECT price FROM ondemand_prices
                WHERE region = %s AND instance_type = %s
                LIMIT 1
            """, (validated_data['region'], validated_data['instance_type']), fetch_one=True)

            if not latest_od_price:
                # Fallback to snapshots if ondemand_prices table is empty
                latest_od_price = execute_query("""
                    SELECT price FROM ondemand_price_snapshots
                    WHERE region = %s AND instance_type = %s
                    ORDER BY captured_at DESC
                    LIMIT 1
                """, (validated_data['region'], validated_data['instance_type']), fetch_one=True)

            baseline_price = latest_od_price['price'] if latest_od_price else 0.0416  # Default t3.medium price

            # Get spot price if in spot mode
            spot_price = 0
            if validated_data['mode'] == 'spot':
                pool_id = validated_data.get('pool_id', f"{validated_data['instance_type']}.{validated_data['az']}")
                latest_spot = execute_query("""
                    SELECT price FROM spot_price_snapshots
                    WHERE pool_id = %s
                    ORDER BY captured_at DESC
                    LIMIT 1
                """, (pool_id,), fetch_one=True)
                spot_price = latest_spot['price'] if latest_spot else baseline_price * 0.3  # Estimate 70% savings

            execute_query("""
                INSERT INTO instances
                (id, client_id, agent_id, instance_type, region, az, ami_id,
                 current_mode, current_pool_id, spot_price, ondemand_price, baseline_ondemand_price,
                 is_active, installed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
            """, (
                validated_data['instance_id'],
                request.client_id,
                agent_id,
                validated_data['instance_type'],
                validated_data['region'],
                validated_data['az'],
                validated_data.get('ami_id'),
                validated_data['mode'],
                validated_data.get('pool_id') if validated_data['mode'] == 'spot' else None,
                spot_price if validated_data['mode'] == 'spot' else 0,
                baseline_price,
                baseline_price
            ))

        # Get agent config
        config_data = execute_query("""
            SELECT
                a.enabled,
                a.auto_switch_enabled,
                a.auto_terminate_enabled,
                a.terminate_wait_seconds,
                a.replica_enabled,
                a.replica_count,
                COALESCE(ac.min_savings_percent, 15.00) as min_savings_percent,
                COALESCE(ac.risk_threshold, 0.30) as risk_threshold,
                COALESCE(ac.max_switches_per_week, 10) as max_switches_per_week,
                COALESCE(ac.min_pool_duration_hours, 2) as min_pool_duration_hours
            FROM agents a
            LEFT JOIN agent_configs ac ON ac.agent_id = a.id
            WHERE a.id = %s
        """, (agent_id,), fetch_one=True)

        log_system_event('agent_registered', 'info',
                        f"Agent {logical_agent_id} registered successfully",
                        request.client_id, agent_id, validated_data['instance_id'])

        logger.info(f"✓ Agent registered successfully: agent_id={agent_id}, logical_id={logical_agent_id}, instance_id={validated_data['instance_id']}, mode={validated_data['mode']}")

        return jsonify({
            'agent_id': agent_id,
            'client_id': request.client_id,
            'config': {
                'enabled': config_data['enabled'],
                'auto_switch_enabled': config_data['auto_switch_enabled'],
                'auto_terminate_enabled': config_data['auto_terminate_enabled'],
                'terminate_wait_seconds': config_data['terminate_wait_seconds'],
                'replica_enabled': config_data['replica_enabled'],
                'replica_count': config_data['replica_count'],
                'min_savings_percent': float(config_data['min_savings_percent']),
                'risk_threshold': float(config_data['risk_threshold']),
                'max_switches_per_week': config_data['max_switches_per_week'],
                'min_pool_duration_hours': config_data['min_pool_duration_hours']
            }
        })

    except Exception as e:
        logger.error(f"Agent registration error: {e}", exc_info=True)
        log_system_event('agent_registration_failed', 'error', str(e), request.client_id)
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/heartbeat', methods=['POST'])
@require_client_auth
def agent_heartbeat(agent_id: str):
    """Update agent heartbeat"""
    data = request.json or {}

    try:
        new_status = data.get('status', 'online')

        # Get previous status and current instance
        prev = execute_query(
            "SELECT status, instance_id FROM agents WHERE id = %s AND client_id = %s",
            (agent_id, request.client_id),
            fetch_one=True
        )

        if not prev:
            return jsonify({'error': 'Agent not found'}), 404

        # If instance_id is being updated, check if it's from a zombie/terminated instance
        new_instance_id = data.get('instance_id')
        if new_instance_id and new_instance_id != prev.get('instance_id'):
            # Check if the new instance is a zombie or terminated
            instance_check = execute_query("""
                SELECT instance_status, is_primary
                FROM instances
                WHERE id = %s
            """, (new_instance_id,), fetch_one=True)

            if instance_check:
                status = instance_check.get('instance_status')
                is_primary = instance_check.get('is_primary')

                if status in ('zombie', 'terminated') or not is_primary:
                    logger.warning(f"Rejecting heartbeat instance_id update from zombie/non-primary {new_instance_id}")
                    # Don't allow zombie instances to update the agent's instance_id
                    new_instance_id = None  # Prevent the update

        # Update heartbeat
        execute_query("""
            UPDATE agents
            SET status = %s,
                last_heartbeat_at = NOW(),
                instance_id = COALESCE(%s, instance_id),
                instance_type = COALESCE(%s, instance_type),
                current_mode = COALESCE(%s, current_mode),
                az = COALESCE(%s, az)
            WHERE id = %s AND client_id = %s
        """, (
            new_status,
            new_instance_id,
            data.get('instance_type'),
            data.get('mode'),
            data.get('az'),
            agent_id,
            request.client_id
        ))

        # Check for status change
        if prev['status'] != new_status:
            if new_status == 'offline':
                create_notification(f"Agent {agent_id} went offline", 'warning', request.client_id)
            elif new_status == 'online' and prev['status'] == 'offline':
                create_notification(f"Agent {agent_id} is back online", 'info', request.client_id)

        # Update client sync time
        execute_query(
            "UPDATE clients SET last_sync_at = NOW() WHERE id = %s",
            (request.client_id,)
        )

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Heartbeat error: {e}")
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/config', methods=['GET'])
@require_client_auth
def get_agent_config(agent_id: str):
    """Get agent configuration"""
    try:
        config_data = execute_query("""
            SELECT
                a.enabled,
                a.auto_switch_enabled,
                a.auto_terminate_enabled,
                a.terminate_wait_seconds,
                a.replica_enabled,
                a.replica_count,
                a.manual_replica_enabled,
                COALESCE(ac.min_savings_percent, 15.00) as min_savings_percent,
                COALESCE(ac.risk_threshold, 0.30) as risk_threshold,
                COALESCE(ac.max_switches_per_week, 10) as max_switches_per_week,
                COALESCE(ac.min_pool_duration_hours, 2) as min_pool_duration_hours
            FROM agents a
            LEFT JOIN agent_configs ac ON ac.agent_id = a.id
            WHERE a.id = %s AND a.client_id = %s
        """, (agent_id, request.client_id), fetch_one=True)

        if not config_data:
            return jsonify({'error': 'Agent not found'}), 404

        return jsonify({
            'enabled': config_data['enabled'],
            'auto_switch_enabled': config_data['auto_switch_enabled'],
            'auto_terminate_enabled': config_data['auto_terminate_enabled'],
            'terminate_wait_seconds': config_data['terminate_wait_seconds'],
            'replica_enabled': config_data['replica_enabled'],
            'replica_count': config_data['replica_count'],
            'manual_replica_enabled': config_data['manual_replica_enabled'],
            'min_savings_percent': float(config_data['min_savings_percent']),
            'risk_threshold': float(config_data['risk_threshold']),
            'max_switches_per_week': config_data['max_switches_per_week'],
            'min_pool_duration_hours': config_data['min_pool_duration_hours']
        })

    except Exception as e:
        logger.error(f"Get config error: {e}")
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/instances-to-terminate', methods=['GET'])
@require_client_auth
def get_instances_to_terminate(agent_id: str):
    """
    Get list of instances that should be terminated by the agent.

    Returns instances that are:
    1. Marked as 'zombie' and past their terminate_wait_seconds
    2. Marked as 'terminated' in replica_instances but not yet terminated in AWS

    The agent's Cleanup worker should poll this endpoint and terminate instances via AWS EC2 API.
    """
    try:
        # Get agent's auto_terminate setting and terminate_wait_seconds
        agent = execute_query("""
            SELECT auto_terminate_enabled, terminate_wait_seconds, region
            FROM agents
            WHERE id = %s AND client_id = %s
        """, (agent_id, request.client_id), fetch_one=True)

        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        instances_to_terminate = []

        # Only proceed if auto_terminate is enabled
        if agent['auto_terminate_enabled']:
            terminate_wait_seconds = agent['terminate_wait_seconds'] or 300

            # Get zombie instances past their termination wait period
            zombie_instances = execute_query("""
                SELECT
                    i.id as instance_id,
                    i.instance_type,
                    i.az,
                    i.instance_status,
                    i.terminated_at,
                    TIMESTAMPDIFF(SECOND, i.updated_at, NOW()) as seconds_since_zombie
                FROM instances i
                WHERE i.instance_status = 'zombie'
                  AND i.is_active = FALSE
                  AND i.region = %s
                  AND TIMESTAMPDIFF(SECOND, i.updated_at, NOW()) >= %s
                  AND (i.termination_attempted_at IS NULL OR i.termination_attempted_at < DATE_SUB(NOW(), INTERVAL 5 MINUTE))
            """, (agent['region'], terminate_wait_seconds), fetch=True)

            for inst in zombie_instances or []:
                instances_to_terminate.append({
                    'instance_id': inst['instance_id'],
                    'instance_type': inst['instance_type'],
                    'az': inst['az'],
                    'reason': 'zombie_timeout',
                    'seconds_waiting': inst['seconds_since_zombie']
                })

            # Get replica instances marked as terminated but not yet terminated in AWS
            terminated_replicas = execute_query("""
                SELECT
                    ri.instance_id,
                    ri.instance_type,
                    ri.az,
                    ri.status,
                    TIMESTAMPDIFF(SECOND, ri.terminated_at, NOW()) as seconds_since_marked
                FROM replica_instances ri
                WHERE ri.agent_id = %s
                  AND ri.status = 'terminated'
                  AND ri.instance_id IS NOT NULL
                  AND ri.instance_id != ''
                  AND (ri.termination_attempted_at IS NULL OR ri.termination_attempted_at < DATE_SUB(NOW(), INTERVAL 5 MINUTE))
            """, (agent_id,), fetch=True)

            for rep in terminated_replicas or []:
                instances_to_terminate.append({
                    'instance_id': rep['instance_id'],
                    'instance_type': rep['instance_type'],
                    'az': rep['az'],
                    'reason': 'replica_terminated',
                    'seconds_since_marked': rep['seconds_since_marked']
                })

        logger.info(f"Agent {agent_id} fetched {len(instances_to_terminate)} instances to terminate")

        return jsonify({
            'instances': instances_to_terminate,
            'auto_terminate_enabled': agent['auto_terminate_enabled'],
            'terminate_wait_seconds': agent.get('terminate_wait_seconds', 300)
        })

    except Exception as e:
        logger.error(f"Get instances to terminate error: {e}")
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/termination-report', methods=['POST'])
@require_client_auth
def receive_termination_report(agent_id: str):
    """
    Receive termination report from agent after terminating instances.

    Request body:
    {
        "instance_id": "i-1234567890abcdef0",
        "success": true/false,
        "error": "error message if failed",
        "terminated_at": "2025-11-25T12:00:00"
    }
    """
    try:
        data = request.json or {}
        instance_id = data.get('instance_id')
        success = data.get('success', False)
        error_message = data.get('error')
        terminated_at = data.get('terminated_at')

        if not instance_id:
            return jsonify({'error': 'instance_id required'}), 400

        if success:
            # Mark instance as actually terminated in AWS
            execute_query("""
                UPDATE instances
                SET
                    instance_status = 'terminated',
                    is_active = FALSE,
                    terminated_at = %s,
                    termination_attempted_at = NOW(),
                    termination_confirmed = TRUE
                WHERE id = %s
            """, (terminated_at or datetime.utcnow(), instance_id))

            # Also mark in replica_instances if it exists
            execute_query("""
                UPDATE replica_instances
                SET
                    status = 'terminated',
                    terminated_at = %s,
                    termination_attempted_at = NOW(),
                    termination_confirmed = TRUE
                WHERE instance_id = %s
            """, (terminated_at or datetime.utcnow(), instance_id))

            logger.info(f"✓ Instance {instance_id} confirmed terminated by agent {agent_id}")

            # Log system event
            execute_query("""
                INSERT INTO system_events (event_type, severity, agent_id, message, metadata)
                VALUES ('instance_terminated', 'info', %s, %s, %s)
            """, (agent_id,
                  f"Instance {instance_id} terminated in AWS",
                  json.dumps({'instance_id': instance_id, 'terminated_at': terminated_at})))
        else:
            # Mark termination attempt but note it failed
            execute_query("""
                UPDATE instances
                SET termination_attempted_at = NOW()
                WHERE id = %s
            """, (instance_id,))

            execute_query("""
                UPDATE replica_instances
                SET termination_attempted_at = NOW()
                WHERE instance_id = %s
            """, (instance_id,))

            logger.error(f"✗ Failed to terminate instance {instance_id}: {error_message}")

            # Log system event
            execute_query("""
                INSERT INTO system_events (event_type, severity, agent_id, message, metadata)
                VALUES ('instance_termination_failed', 'warning', %s, %s, %s)
            """, (agent_id,
                  f"Failed to terminate instance {instance_id}: {error_message}",
                  json.dumps({'instance_id': instance_id, 'error': error_message})))

        return jsonify({
            'success': True,
            'message': 'Termination report recorded'
        })

    except Exception as e:
        logger.error(f"Termination report error: {e}")
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/rebalance-recommendation', methods=['POST'])
@require_client_auth
def handle_rebalance_recommendation(agent_id: str):
    """Handle EC2 rebalance recommendations with risk analysis"""
    data = request.json or {}

    try:
        instance_id = data.get('instance_id')
        detected_at = data.get('detected_at')

        # Get agent details
        agent = execute_query("""
            SELECT current_pool_id, instance_type, region, az, current_mode
            FROM agents
            WHERE id = %s AND client_id = %s
        """, (agent_id, request.client_id), fetch_one=True)

        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        # Update agent rebalance timestamp
        execute_query("""
            UPDATE agents
            SET last_rebalance_recommendation_at = NOW()
            WHERE id = %s
        """, (agent_id,))

        # Calculate risk score for current pool
        # Simple risk calculation based on recent interruptions
        interruptions = execute_query("""
            SELECT COUNT(*) as count
            FROM spot_interruption_events
            WHERE pool_id = %s
              AND detected_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """, (agent['current_pool_id'],), fetch_one=True)

        interruption_count = interruptions['count'] if interruptions else 0
        risk_score = min(interruption_count / 30.0, 1.0)  # Normalize to 0-1

        # Insert into termination_events table
        execute_query("""
            INSERT INTO termination_events (
                agent_id, instance_id, event_type,
                detected_at, status, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            agent_id,
            instance_id,
            'rebalance_recommendation',
            detected_at or datetime.utcnow(),
            'detected',
            json.dumps({'risk_score': risk_score, 'current_pool': agent['current_pool_id']})
        ))

        # Find alternative pools with lower risk
        alternative_pools = execute_query("""
            SELECT sp.id, sp.pool_name, sp.instance_type, sp.az,
                   COALESCE(COUNT(sie.id), 0) as interruption_count
            FROM spot_pools sp
            LEFT JOIN spot_interruption_events sie
                ON sp.id = sie.pool_id
                AND sie.detected_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            WHERE sp.instance_type = %s
              AND sp.region = %s
              AND sp.az != %s
              AND sp.is_active = TRUE
            GROUP BY sp.id
            ORDER BY interruption_count ASC
            LIMIT 1
        """, (agent['instance_type'], agent['region'], agent['az']), fetch=True)

        # Determine action based on risk
        if risk_score > 0.30 and alternative_pools:
            action = 'switch'
            target_pool = alternative_pools[0]
            reason = f"Current pool has elevated interruption risk ({risk_score:.2%})"
        else:
            action = 'monitor'
            target_pool = None
            reason = f"Risk is acceptable ({risk_score:.2%}), continuing to monitor"

        # Log system event
        log_system_event(
            'rebalance_recommendation',
            'warning',
            f"Rebalance recommendation for {instance_id}. Risk: {risk_score:.2%}. Action: {action}",
            request.client_id,
            agent_id,
            metadata={'risk_score': risk_score, 'action': action}
        )

        response = {
            'success': True,
            'action': action,
            'risk_score': risk_score,
            'reason': reason
        }

        if target_pool:
            response.update({
                'target_mode': 'spot',
                'target_pool_id': target_pool['id'],
                'target_pool_name': target_pool['pool_name']
            })

        return jsonify(response)

    except Exception as e:
        logger.error(f"Rebalance recommendation error: {e}")
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/replica-config', methods=['GET'])
@require_client_auth
def get_replica_config(agent_id: str):
    """Get replica configuration for agent"""
    try:
        config_data = execute_query("""
            SELECT replica_enabled, replica_count
            FROM agents
            WHERE id = %s AND client_id = %s
        """, (agent_id, request.client_id), fetch_one=True)

        if not config_data:
            return jsonify({'error': 'Agent not found'}), 404

        return jsonify({
            'enabled': config_data['replica_enabled'],
            'count': config_data['replica_count']
        })

    except Exception as e:
        logger.error(f"Get replica config error: {e}")
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/decide', methods=['POST'])
@require_client_auth
def get_decision(agent_id: str):
    """Get switching decision from decision engine"""
    data = request.json

    try:
        instance = data['instance']
        pricing = data['pricing']

        # Get agent config
        config_data = execute_query("""
            SELECT
                a.enabled,
                a.auto_switch_enabled,
                COALESCE(ac.min_savings_percent, 15.00) as min_savings_percent,
                COALESCE(ac.risk_threshold, 0.30) as risk_threshold,
                COALESCE(ac.max_switches_per_week, 10) as max_switches_per_week,
                COALESCE(ac.min_pool_duration_hours, 2) as min_pool_duration_hours
            FROM agents a
            LEFT JOIN agent_configs ac ON ac.agent_id = a.id
            WHERE a.id = %s AND a.client_id = %s
        """, (agent_id, request.client_id), fetch_one=True)

        if not config_data or not config_data['enabled']:
            return jsonify({
                'instance_id': instance.get('instance_id'),
                'risk_score': 0.0,
                'recommended_action': 'stay',
                'recommended_mode': instance.get('current_mode'),
                'recommended_pool_id': instance.get('current_pool_id'),
                'expected_savings_per_hour': 0.0,
                'allowed': False,
                'reason': 'Agent disabled'
            })

        # Get recent switches count
        recent_switches = execute_query("""
            SELECT COUNT(*) as count
            FROM switches
            WHERE agent_id = %s AND initiated_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """, (agent_id,), fetch_one=True)

        # Get last switch time
        last_switch = execute_query("""
            SELECT initiated_at FROM switches
            WHERE agent_id = %s
            ORDER BY initiated_at DESC
            LIMIT 1
        """, (agent_id,), fetch_one=True)

        # Make decision using decision engine manager
        from core.decision_engine import decision_engine_manager
        decision = decision_engine_manager.make_decision(
            instance=instance,
            pricing=pricing,
            config_data=config_data,
            recent_switches_count=recent_switches['count'] if recent_switches else 0,
            last_switch_time=last_switch['initiated_at'] if last_switch else None
        )

        # Store decision in database
        execute_query("""
            INSERT INTO risk_scores (
                client_id, instance_id, agent_id, risk_score, recommended_action,
                recommended_pool_id, recommended_mode, expected_savings_per_hour,
                allowed, reason, model_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.client_id, instance.get('instance_id'), agent_id,
            decision.get('risk_score'), decision.get('recommended_action'),
            decision.get('recommended_pool_id'), decision.get('recommended_mode'),
            decision.get('expected_savings_per_hour'), decision.get('allowed'),
            decision.get('reason'), decision_engine_manager.engine_version
        ))

        # Log decision to history table for analytics
        try:
            execute_query("""
                INSERT INTO agent_decision_history (
                    agent_id, client_id, decision_type, recommended_action,
                    recommended_pool_id, risk_score, expected_savings,
                    current_mode, current_pool_id, current_price, decision_time
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                agent_id,
                request.client_id,
                decision.get('recommended_action', 'stay'),
                decision.get('recommended_action'),
                decision.get('recommended_pool_id'),
                decision.get('risk_score', 0),
                decision.get('expected_savings_per_hour', 0),
                instance.get('current_mode'),
                instance.get('current_pool_id'),
                pricing.get('current_spot_price', 0)
            ))
        except Exception as log_error:
            # Don't fail the request if logging fails
            logger.warning(f"Failed to log decision history: {log_error}")

        return jsonify(decision)

    except Exception as e:
        logger.error(f"Decision error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/switch-recommendation', methods=['GET'])
@require_client_auth
def get_switch_recommendation(agent_id: str):
    """
    Get ML-based switch recommendation for an agent (ALWAYS returns suggestion).
    This endpoint provides recommendations regardless of auto_switch_enabled setting.
    Use this to show suggestions to users even when auto-switch is disabled.
    """
    try:
        # Get agent and instance details
        agent_data = execute_query("""
            SELECT
                a.id, a.hostname, a.enabled, a.auto_switch_enabled,
                a.current_mode, a.current_pool_id, a.instance_id,
                i.instance_type, i.region, i.az, i.spot_price, i.ondemand_price,
                sp.pool_name, sp.az as pool_az,
                COALESCE(ac.min_savings_percent, 15.00) as min_savings_percent,
                COALESCE(ac.risk_threshold, 0.30) as risk_threshold
            FROM agents a
            JOIN instances i ON a.instance_id = i.id
            LEFT JOIN spot_pools sp ON i.current_pool_id = sp.id
            LEFT JOIN agent_configs ac ON ac.agent_id = a.id
            WHERE a.id = %s AND a.client_id = %s
        """, (agent_id, request.client_id), fetch_one=True)

        if not agent_data:
            return jsonify({'error': 'Agent not found'}), 404

        # Get recent pricing data
        pricing_data = execute_query("""
            SELECT pool_id, spot_price, time_bucket
            FROM pricing_snapshots_clean
            WHERE pool_id = %s
            ORDER BY time_bucket DESC
            LIMIT 10
        """, (agent_data['current_pool_id'],), fetch=True)

        # Get alternative pools
        alternative_pools = execute_query("""
            SELECT
                sp.id, sp.pool_name, sp.instance_type, sp.az,
                psc.spot_price, psc.time_bucket
            FROM spot_pools sp
            JOIN pricing_snapshots_clean psc ON sp.id = psc.pool_id
            WHERE sp.instance_type = %s
              AND sp.region = %s
              AND sp.id != %s
              AND psc.time_bucket >= NOW() - INTERVAL 5 MINUTE
            ORDER BY psc.spot_price ASC
            LIMIT 5
        """, (agent_data['instance_type'], agent_data['region'], agent_data['current_pool_id']), fetch=True)

        # Prepare data for decision engine
        instance_info = {
            'instance_id': agent_data['instance_id'],
            'instance_type': agent_data['instance_type'],
            'region': agent_data['region'],
            'current_mode': agent_data['current_mode'],
            'current_pool_id': agent_data['current_pool_id']
        }

        pricing_info = {
            'spot_price': float(agent_data['spot_price']) if agent_data['spot_price'] else 0,
            'ondemand_price': float(agent_data['ondemand_price']) if agent_data['ondemand_price'] else 0,
            'pool_id': agent_data['current_pool_id']
        }

        # Get recommendation from decision engine
        from core.decision_engine import decision_engine_manager
        if decision_engine_manager.engine and decision_engine_manager.models_loaded:
            decision = decision_engine_manager.engine.make_decision(
                instance_info, pricing_info, {'alternative_pools': alternative_pools}
            )
        else:
            # Fallback: simple rule-based logic
            savings_percent = 0
            if agent_data['ondemand_price'] and agent_data['spot_price']:
                savings_percent = ((agent_data['ondemand_price'] - agent_data['spot_price']) / agent_data['ondemand_price']) * 100

            decision = {
                'decision_type': 'stay_spot' if agent_data['current_mode'] == 'spot' else 'stay_ondemand',
                'recommended_pool_id': agent_data['current_pool_id'],
                'risk_score': 0.3,
                'expected_savings': float(agent_data['ondemand_price'] - agent_data['spot_price']) if agent_data['ondemand_price'] and agent_data['spot_price'] else 0,
                'confidence': 0.6,
                'reason': f'Current configuration optimal ({savings_percent:.1f}% savings)'
            }

        # Add auto_switch status to response
        response = {
            **decision,
            'agent_id': agent_id,
            'auto_switch_enabled': agent_data['auto_switch_enabled'],
            'will_auto_execute': agent_data['auto_switch_enabled'] and decision.get('decision_type') not in ('stay_spot', 'stay_ondemand'),
            'current_pool': {
                'id': agent_data['current_pool_id'],
                'name': agent_data.get('pool_name'),
                'az': agent_data.get('pool_az')
            },
            'alternative_pools': [
                {
                    'id': p['id'],
                    'name': p['pool_name'],
                    'az': p['az'],
                    'spot_price': float(p['spot_price'])
                } for p in (alternative_pools or [])
            ]
        }

        logger.info(f"Switch recommendation for agent {agent_id}: {decision.get('decision_type')} (auto_switch={agent_data['auto_switch_enabled']})")

        return jsonify(response)

    except Exception as e:
        logger.error(f"Switch recommendation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/issue-switch-command', methods=['POST'])
@require_client_auth
def issue_switch_command(agent_id: str):
    """
    Issue a switch command to an agent (CHECKS auto_switch_enabled).
    If auto_switch is disabled, returns error. If enabled, creates switch command.

    Request body:
    {
        "target_mode": "spot" | "ondemand",
        "target_pool_id": 123,  # required for spot mode
        "reason": "ML recommendation",
        "priority": 5  # 1-10, default 5
    }
    """
    try:
        data = request.json or {}

        # Get agent configuration including terminate settings
        agent = execute_query("""
            SELECT id, hostname, auto_switch_enabled, auto_terminate_enabled,
                   terminate_wait_seconds, enabled, instance_id, current_mode, current_pool_id
            FROM agents
            WHERE id = %s AND client_id = %s
        """, (agent_id, request.client_id), fetch_one=True)

        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        if not agent['enabled']:
            return jsonify({
                'error': 'Agent is disabled',
                'hint': 'Enable the agent first'
            }), 400

        # CHECK AUTO_SWITCH_ENABLED - This is the key check
        if not agent['auto_switch_enabled']:
            return jsonify({
                'error': 'Auto-switch is disabled for this agent',
                'hint': 'Enable auto_switch_enabled in agent settings, or use manual switch from UI',
                'auto_switch_enabled': False
            }), 403

        # Validate request
        target_mode = data.get('target_mode')
        if target_mode not in ('spot', 'ondemand'):
            return jsonify({'error': 'Invalid target_mode'}), 400

        target_pool_id = data.get('target_pool_id')
        if target_mode == 'spot' and not target_pool_id:
            return jsonify({'error': 'target_pool_id required for spot mode'}), 400

        # Don't create redundant command if already in target state
        if agent['current_mode'] == target_mode and (target_mode != 'spot' or agent['current_pool_id'] == target_pool_id):
            return jsonify({
                'success': False,
                'message': 'Agent already in target state',
                'current_mode': agent['current_mode'],
                'current_pool_id': agent['current_pool_id']
            }), 200

        # Determine terminate_wait_seconds based on auto_terminate setting
        # If auto_terminate is disabled, set to 0 to signal agent NOT to terminate old instance
        if agent['auto_terminate_enabled']:
            terminate_wait = agent['terminate_wait_seconds'] or 300
        else:
            terminate_wait = 0  # Signal: DO NOT terminate old instance

        # Create switch command
        command_id = generate_uuid()
        execute_query("""
            INSERT INTO commands (
                id, agent_id, client_id, instance_id,
                target_mode, target_pool_id, priority,
                terminate_wait_seconds, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
        """, (
            command_id,
            agent_id,
            request.client_id,
            agent['instance_id'],
            target_mode,
            target_pool_id,
            data.get('priority', 5),
            terminate_wait
        ))

        logger.info(f"✓ Switch command issued for agent {agent_id}: {target_mode} (pool: {target_pool_id}), auto_terminate={agent['auto_terminate_enabled']}, terminate_wait={terminate_wait}s")

        create_notification(
            f"Switch command issued to {agent.get('hostname', agent_id)}: {target_mode}",
            'info',
            request.client_id
        )

        return jsonify({
            'success': True,
            'command_id': command_id,
            'agent_id': agent_id,
            'target_mode': target_mode,
            'target_pool_id': target_pool_id,
            'reason': data.get('reason', 'Manual command'),
            'message': 'Switch command queued. Agent will execute on next heartbeat.',
            'auto_switch_enabled': True
        }), 201

    except Exception as e:
        logger.error(f"Issue switch command error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/statistics', methods=['GET'])
@require_client_auth
def get_agent_statistics(agent_id: str):
    """
    Get decision engine statistics for an agent.

    Returns metrics on decisions, switches, success rates, and savings.
    """
    try:
        # Get switch statistics
        switch_stats = execute_query("""
            SELECT
                COUNT(*) as total_switches,
                AVG(downtime_seconds) as avg_downtime,
                SUM(savings_impact * 24) as total_savings,
                SUM(CASE WHEN trigger = 'automatic' THEN 1 ELSE 0 END) as automatic_switches,
                SUM(CASE WHEN trigger = 'manual' THEN 1 ELSE 0 END) as manual_switches
            FROM switches
            WHERE agent_id = %s
        """, (agent_id,), fetch_one=True)

        # Get decision counts from agent_decision_history if exists
        decision_stats = execute_query("""
            SELECT
                COUNT(*) as total_decisions,
                AVG(confidence) as avg_confidence
            FROM agent_decision_history
            WHERE agent_id = %s
        """, (agent_id,), fetch_one=True)

        # Calculate success rate
        total_switches = switch_stats['total_switches'] if switch_stats else 0
        total_decisions = decision_stats['total_decisions'] if decision_stats else total_switches
        success_rate = (total_switches / total_decisions) if total_decisions > 0 else 0

        # Get last decision time
        last_decision = execute_query("""
            SELECT MAX(created_at) as last_decision_at
            FROM agent_decision_history
            WHERE agent_id = %s
        """, (agent_id,), fetch_one=True)

        statistics = {
            'total_decisions': total_decisions or 0,
            'switches_executed': total_switches or 0,
            'switches_recommended': total_decisions or 0,
            'success_rate': round(success_rate, 2),
            'average_confidence': round(float(decision_stats['avg_confidence'] or 0.0), 2),
            'last_decision_at': last_decision['last_decision_at'].isoformat() if last_decision and last_decision['last_decision_at'] else None,
            'decisions_by_trigger': {
                'automatic': switch_stats['automatic_switches'] if switch_stats else 0,
                'manual': switch_stats['manual_switches'] if switch_stats else 0
            },
            'avg_downtime_seconds': int(switch_stats['avg_downtime'] or 0) if switch_stats else 0,
            'total_savings_generated': float(switch_stats['total_savings'] or 0.0) if switch_stats else 0.0
        }

        return jsonify({
            'agent_id': agent_id,
            'statistics': statistics
        })

    except Exception as e:
        logger.error(f"Get agent statistics error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@agents_bp.route('/api/agents/<agent_id>/emergency-status', methods=['GET'])
@require_client_auth
def get_emergency_status(agent_id: str):
    """
    Check if agent is in emergency/fallback mode.

    Returns emergency mode indicators and recent emergency events.
    """
    try:
        # Get agent info
        agent = execute_query("""
            SELECT
                id,
                auto_switch_enabled,
                manual_replica_enabled,
                emergency_replica_count,
                last_rebalance_recommendation_at,
                last_termination_notice_at
            FROM agents
            WHERE id = %s
        """, (agent_id,), fetch_one=True)

        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        # Get last emergency event
        last_emergency = execute_query("""
            SELECT
                created_at as timestamp,
                event_type as type,
                message as action_taken
            FROM system_events
            WHERE (event_type LIKE '%emergency%' OR event_type LIKE '%termination%' OR event_type LIKE '%rebalance%')
            AND message LIKE %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (f'%{agent_id}%',), fetch_one=True)

        # Count termination notices in last 24h
        termination_count = execute_query("""
            SELECT COUNT(*) as count
            FROM spot_interruption_events
            WHERE agent_id = %s
            AND event_type IN ('termination_notice', 'rebalance_recommendation')
            AND event_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        """, (agent_id,), fetch_one=True)

        status = {
            'agent_id': agent_id,
            'emergency_mode_active': False,  # Would be determined by replica coordinator state
            'rebalance_only_mode': agent['manual_replica_enabled'] if agent else False,
            'ml_models_loaded': True,  # Would check decision_engine_manager.models_loaded
            'decision_engine_active': agent['auto_switch_enabled'] if agent else False,
            'last_emergency_event': {
                'timestamp': last_emergency['timestamp'].isoformat() if last_emergency and last_emergency['timestamp'] else None,
                'type': last_emergency['type'] if last_emergency else None,
                'action_taken': last_emergency['action_taken'] if last_emergency else None,
                'outcome': 'success'  # Placeholder
            } if last_emergency else None,
            'emergency_replicas_count': agent['emergency_replica_count'] if agent else 0,
            'termination_notices_24h': termination_count['count'] if termination_count else 0
        }

        return jsonify(status)

    except Exception as e:
        logger.error(f"Get emergency status error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
