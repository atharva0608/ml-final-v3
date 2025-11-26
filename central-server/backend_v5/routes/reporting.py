from flask import Blueprint, request, jsonify
import logging
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import success_response, error_response, format_decimal, generate_uuid, create_notification, log_system_event
import json
from datetime import datetime

logger = logging.getLogger(__name__)
reporting_bp = Blueprint('reporting', __name__)

@reporting_bp.route('/api/agents/<agent_id>/pricing-report', methods=['POST'])
@require_client_auth
def pricing_report(agent_id: str):
    """Receive pricing data from agent"""
    data = request.json

    try:
        instance = data.get('instance', {})
        pricing = data.get('pricing', {})

        # Update instance pricing
        execute_query("""
            UPDATE instances
            SET ondemand_price = %s, spot_price = %s, updated_at = NOW()
            WHERE id = %s AND client_id = %s
        """, (
            pricing.get('on_demand_price'),
            pricing.get('current_spot_price'),
            instance.get('instance_id'),
            request.client_id
        ))

        # Store pricing report
        report_id = generate_uuid()
        execute_query("""
            INSERT INTO pricing_reports (
                id, agent_id, instance_id, instance_type, region, az,
                current_mode, current_pool_id, on_demand_price, current_spot_price,
                cheapest_pool_id, cheapest_pool_price, spot_pools, collected_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            report_id,
            agent_id,
            instance.get('instance_id'),
            instance.get('instance_type'),
            instance.get('region'),
            instance.get('az'),
            instance.get('mode'),
            instance.get('pool_id'),
            pricing.get('on_demand_price'),
            pricing.get('current_spot_price'),
            pricing.get('cheapest_pool', {}).get('pool_id') if pricing.get('cheapest_pool') else None,
            pricing.get('cheapest_pool', {}).get('price') if pricing.get('cheapest_pool') else None,
            json.dumps(pricing.get('spot_pools', [])),
            pricing.get('collected_at')
        ))

        # Store spot pool prices
        for pool in pricing.get('spot_pools', []):
            pool_id = pool['pool_id']

            # Ensure pool exists
            execute_query("""
                INSERT INTO spot_pools (id, instance_type, region, az)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE updated_at = NOW()
            """, (pool_id, instance.get('instance_type'), instance.get('region'), pool['az']))

            # Store price snapshot
            execute_query("""
                INSERT INTO spot_price_snapshots (pool_id, price)
                VALUES (%s, %s)
            """, (pool_id, pool['price']))

        # Store on-demand price snapshot
        if pricing.get('on_demand_price'):
            execute_query("""
                INSERT INTO ondemand_price_snapshots (region, instance_type, price)
                VALUES (%s, %s, %s)
            """, (instance.get('region'), instance.get('instance_type'), pricing['on_demand_price']))

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Pricing report error: {e}")
        return jsonify({'error': str(e)}), 500

@reporting_bp.route('/api/agents/<agent_id>/switch-report', methods=['POST'])
@require_client_auth
def switch_report(agent_id: str):
    """Record switch event"""
    data = request.json

    try:
        old_inst = data.get('old_instance', {})
        new_inst = data.get('new_instance', {})
        timing = data.get('timing', {})
        prices = data.get('pricing', {})

        # Get agent's auto_terminate setting
        agent = execute_query("""
            SELECT auto_terminate_enabled FROM agents WHERE id = %s
        """, (agent_id,), fetch_one=True)

        auto_terminate_enabled = agent.get('auto_terminate_enabled', True) if agent else True

        # Calculate savings impact
        old_price = prices.get('old_spot') or prices.get('on_demand', 0)
        new_price = prices.get('new_spot') or prices.get('on_demand', 0)
        savings_impact = old_price - new_price

        # Insert switch record
        switch_id = generate_uuid()
        execute_query("""
            INSERT INTO switches (
                id, client_id, agent_id, command_id,
                old_instance_id, old_instance_type, old_region, old_az, old_mode, old_pool_id, old_ami_id,
                new_instance_id, new_instance_type, new_region, new_az, new_mode, new_pool_id, new_ami_id,
                on_demand_price, old_spot_price, new_spot_price, savings_impact,
                event_trigger, trigger_type, timing_data,
                initiated_at, ami_created_at, instance_launched_at, instance_ready_at, old_terminated_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s
            )
        """, (
            switch_id, request.client_id, agent_id, data.get('command_id'),
            old_inst.get('instance_id'), old_inst.get('instance_type'), old_inst.get('region'),
            old_inst.get('az'), old_inst.get('mode'), old_inst.get('pool_id'), old_inst.get('ami_id'),
            new_inst.get('instance_id'), new_inst.get('instance_type'), new_inst.get('region'),
            new_inst.get('az'), new_inst.get('mode'), new_inst.get('pool_id'), new_inst.get('ami_id'),
            prices.get('on_demand'), prices.get('old_spot'), prices.get('new_spot'), savings_impact,
            data.get('trigger'), data.get('trigger'), json.dumps(timing),
            timing.get('initiated_at'), timing.get('ami_created_at'),
            timing.get('instance_launched_at'), timing.get('instance_ready_at'),
            timing.get('old_terminated_at')
        ))

        # Handle old instance based on auto_terminate setting
        if auto_terminate_enabled and timing.get('old_terminated_at'):
            # Mark old instance as terminated
            execute_query("""
                UPDATE instances
                SET is_active = FALSE,
                    terminated_at = %s,
                    instance_status = 'terminated',
                    is_primary = FALSE
                WHERE id = %s AND client_id = %s
            """, (timing.get('old_terminated_at'), old_inst.get('instance_id'), request.client_id))
            logger.info(f"Old instance {old_inst.get('instance_id')} marked as terminated (auto_terminate=ON)")
        else:
            # Mark old instance as zombie (still running but not primary)
            execute_query("""
                UPDATE instances
                SET instance_status = 'zombie',
                    is_primary = FALSE,
                    is_active = FALSE
                WHERE id = %s AND client_id = %s
            """, (old_inst.get('instance_id'), request.client_id))
            logger.info(f"Old instance {old_inst.get('instance_id')} marked as zombie (auto_terminate=OFF)")

        # Register new instance as primary
        execute_query("""
            INSERT INTO instances (
                id, client_id, agent_id, instance_type, region, az, ami_id,
                current_mode, current_pool_id, spot_price, ondemand_price,
                is_active, instance_status, is_primary, installed_at, last_switch_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, 'running_primary', TRUE, %s, %s)
            ON DUPLICATE KEY UPDATE
                current_mode = VALUES(current_mode),
                current_pool_id = VALUES(current_pool_id),
                spot_price = VALUES(spot_price),
                is_active = TRUE,
                instance_status = 'running_primary',
                is_primary = TRUE,
                last_switch_at = VALUES(last_switch_at)
        """, (
            new_inst.get('instance_id'), request.client_id, agent_id,
            new_inst.get('instance_type'), new_inst.get('region'), new_inst.get('az'),
            new_inst.get('ami_id'), new_inst.get('mode'), new_inst.get('pool_id'),
            prices.get('new_spot', 0), prices.get('on_demand'),
            timing.get('instance_launched_at'), timing.get('instance_launched_at')
        ))

        # Update agent with new instance info
        execute_query("""
            UPDATE agents
            SET instance_id = %s,
                current_mode = %s,
                current_pool_id = %s,
                last_switch_at = NOW()
            WHERE id = %s
        """, (
            new_inst.get('instance_id'),
            new_inst.get('mode'),
            new_inst.get('pool_id'),
            agent_id
        ))

        # Update total savings
        if savings_impact > 0:
            execute_query("""
                UPDATE clients
                SET total_savings = total_savings + %s
                WHERE id = %s
            """, (savings_impact * 24, request.client_id))

        create_notification(
            f"Instance switched: {new_inst.get('instance_id')} - Saved ${savings_impact:.4f}/hr",
            'info',
            request.client_id
        )

        log_system_event('switch_completed', 'info',
                        f"Switch from {old_inst.get('instance_id')} to {new_inst.get('instance_id')}",
                        request.client_id, agent_id, new_inst.get('instance_id'),
                        metadata={'savings_impact': float(savings_impact)})

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Switch report error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@reporting_bp.route('/api/agents/<agent_id>/termination', methods=['POST'])
@require_client_auth
def report_termination(agent_id: str):
    """Report instance termination"""
    data = request.json or {}

    try:
        reason = data.get('reason', 'Unknown')

        # Update agent status
        execute_query("""
            UPDATE agents
            SET status = 'offline',
                terminated_at = NOW()
            WHERE id = %s AND client_id = %s
        """, (agent_id, request.client_id))

        create_notification(
            f"Agent {agent_id} terminated: {reason}",
            'warning',
            request.client_id
        )

        log_system_event('instance_terminated', 'warning',
                        reason, request.client_id, agent_id, metadata=data)

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Termination report error: {e}")
        return jsonify({'error': str(e)}), 500

@reporting_bp.route('/api/agents/<agent_id>/cleanup-report', methods=['POST'])
@require_client_auth
def receive_cleanup_report(agent_id: str):
    """Receive and log cleanup operation results from agents"""
    data = request.json or {}

    try:
        timestamp = data.get('timestamp')
        snapshots = data.get('snapshots', {})
        amis = data.get('amis', {})

        # Count totals
        deleted_snapshots = len(snapshots.get('deleted', []))
        deleted_amis = len(amis.get('deleted_amis', []))
        failed_snapshots = len(snapshots.get('failed', []))
        failed_amis = len(amis.get('failed', []))
        total_failed = failed_snapshots + failed_amis

        # Insert into cleanup_logs table
        execute_query("""
            INSERT INTO cleanup_logs (
                agent_id, client_id, cleanup_type,
                deleted_snapshots_count, deleted_amis_count, failed_count,
                details, cutoff_date, executed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            agent_id,
            request.client_id,
            'full',
            deleted_snapshots,
            deleted_amis,
            total_failed,
            json.dumps(data),
            snapshots.get('cutoff_date'),
            timestamp or datetime.utcnow()
        ))

        # Update agent's last_cleanup_at
        execute_query("""
            UPDATE agents
            SET last_cleanup_at = NOW()
            WHERE id = %s AND client_id = %s
        """, (agent_id, request.client_id))

        # Log system event
        log_system_event(
            'cleanup_completed',
            'info',
            f"Cleaned {deleted_snapshots} snapshots, {deleted_amis} AMIs. Failed: {total_failed}",
            request.client_id,
            agent_id,
            metadata=data
        )

        logger.info(f"Cleanup report received from agent {agent_id}: {deleted_snapshots} snapshots, {deleted_amis} AMIs deleted")

        return jsonify({
            'success': True,
            'message': 'Cleanup report recorded',
            'deleted_snapshots': deleted_snapshots,
            'deleted_amis': deleted_amis,
            'failed_count': total_failed
        })

    except Exception as e:
        logger.error(f"Cleanup report error: {e}")
        return jsonify({'error': str(e)}), 500
