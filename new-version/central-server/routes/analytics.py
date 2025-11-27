from flask import Blueprint, request, jsonify, Response
import logging
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import success_response, error_response, format_decimal
import json
from datetime import datetime
import io
import csv

logger = logging.getLogger(__name__)
analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/api/client/<client_id>/savings', methods=['GET'])
def get_client_savings(client_id: str):
    """Get savings data for charts"""
    range_param = request.args.get('range', 'monthly')

    try:
        if range_param == 'monthly':
            savings = execute_query("""
                SELECT
                    MONTHNAME(CONCAT(year, '-', LPAD(month, 2, '0'), '-01')) as name,
                    baseline_cost as onDemandCost,
                    actual_cost as modelCost,
                    savings
                FROM client_savings_monthly
                WHERE client_id = %s
                ORDER BY year DESC, month DESC
                LIMIT 12
            """, (client_id,), fetch=True)

            savings = list(reversed(savings)) if savings else []

            return jsonify([{
                'name': s['name'],
                'savings': float(s['savings'] or 0),
                'onDemandCost': float(s['onDemandCost'] or 0),
                'modelCost': float(s['modelCost'] or 0)
            } for s in savings])

        return jsonify([])

    except Exception as e:
        logger.error(f"Get savings error: {e}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/client/<client_id>/switch-history', methods=['GET'])
def get_switch_history(client_id: str):
    """Get switch history"""
    instance_id = request.args.get('instance_id')

    try:
        query = """
            SELECT *
            FROM switches
            WHERE client_id = %s
        """
        params = [client_id]

        if instance_id:
            query += " AND (old_instance_id = %s OR new_instance_id = %s)"
            params.extend([instance_id, instance_id])

        query += " ORDER BY initiated_at DESC LIMIT 100"

        history = execute_query(query, tuple(params), fetch=True)

        return jsonify([{
            'id': h['id'],
            'oldInstanceId': h['old_instance_id'],
            'newInstanceId': h['new_instance_id'],
            'timestamp': (h['instance_launched_at'] or h['ami_created_at'] or h['initiated_at']).isoformat() if (h.get('instance_launched_at') or h.get('ami_created_at') or h.get('initiated_at')) else datetime.now().isoformat(),
            'fromMode': h['old_mode'],
            'toMode': h['new_mode'],
            'fromPool': h['old_pool_id'] or 'n/a',
            'toPool': h['new_pool_id'] or 'n/a',
            'trigger': h['event_trigger'] or 'manual',
            'price': float(h['new_spot_price'] or 0) if h['new_mode'] == 'spot' else float(h['on_demand_price'] or 0),
            'savingsImpact': float(h['savings_impact'] or 0)
        } for h in history or []])

    except Exception as e:
        logger.error(f"Get switch history error: {e}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/client/<client_id>/export/savings', methods=['GET'])
def export_client_savings(client_id: str):
    """Export savings data as CSV"""
    try:
        # Get savings data
        savings = execute_query("""
            SELECT
                year,
                month,
                MONTHNAME(CONCAT(year, '-', LPAD(month, 2, '0'), '-01')) as month_name,
                baseline_cost,
                actual_cost,
                savings
            FROM client_savings_monthly
            WHERE client_id = %s
            ORDER BY year DESC, month DESC
        """, (client_id,), fetch=True)

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['Year', 'Month', 'Month Name', 'On-Demand Cost ($)', 'Actual Cost ($)', 'Savings ($)'])

        # Write data
        for s in (savings or []):
            writer.writerow([
                s['year'],
                s['month'],
                s['month_name'],
                f"{float(s['baseline_cost'] or 0):.2f}",
                f"{float(s['actual_cost'] or 0):.2f}",
                f"{float(s['savings'] or 0):.2f}"
            ])

        # Prepare response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=client_{client_id}_savings.csv'}
        )

    except Exception as e:
        logger.error(f"Export savings error: {e}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/client/<client_id>/export/switch-history', methods=['GET'])
def export_switch_history(client_id: str):
    """Export switch history as CSV"""
    try:
        # Get switch history
        history = execute_query("""
            SELECT *
            FROM switches
            WHERE client_id = %s
            ORDER BY initiated_at DESC
        """, (client_id,), fetch=True)

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['Timestamp', 'Old Instance ID', 'New Instance ID', 'From Mode', 'To Mode',
                        'From Pool', 'To Pool', 'Trigger', 'Price ($)', 'Savings Impact ($/hr)'])

        # Write data
        for h in (history or []):
            timestamp = (h.get('instance_launched_at') or h.get('ami_created_at') or h.get('initiated_at')).isoformat() if (h.get('instance_launched_at') or h.get('ami_created_at') or h.get('initiated_at')) else ''
            price = float(h['new_spot_price'] or 0) if h['new_mode'] == 'spot' else float(h['on_demand_price'] or 0)

            writer.writerow([
                timestamp,
                h['old_instance_id'] or 'N/A',
                h['new_instance_id'] or 'N/A',
                h['old_mode'] or 'N/A',
                h['new_mode'] or 'N/A',
                h['old_pool_id'] or 'N/A',
                h['new_pool_id'] or 'N/A',
                h['event_trigger'] or 'manual',
                f"{price:.6f}",
                f"{float(h['savings_impact'] or 0):.6f}"
            ])

        # Prepare response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=client_{client_id}_switch_history.csv'}
        )

    except Exception as e:
        logger.error(f"Export switch history error: {e}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/admin/export/global-stats', methods=['GET'])
def export_global_stats():
    """Export global statistics as CSV"""
    try:
        # Get top clients by savings
        clients = execute_query("""
            SELECT
                c.id,
                c.name,
                c.email,
                c.total_savings,
                c.created_at,
                COUNT(DISTINCT i.id) as instance_count,
                COUNT(DISTINCT a.id) as agent_count
            FROM clients c
            LEFT JOIN instances i ON i.client_id = c.id AND i.is_active = TRUE
            LEFT JOIN agents a ON a.client_id = c.id AND a.enabled = TRUE
            WHERE c.is_active = TRUE
            GROUP BY c.id, c.name, c.email, c.total_savings, c.created_at
            ORDER BY c.total_savings DESC
        """, fetch=True)

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['Client ID', 'Name', 'Email', 'Total Savings ($)', 'Active Instances',
                        'Active Agents', 'Created At'])

        # Write data
        for client in (clients or []):
            writer.writerow([
                client['id'],
                client['name'],
                client['email'],
                f"{float(client['total_savings'] or 0):.2f}",
                client['instance_count'] or 0,
                client['agent_count'] or 0,
                client['created_at'].isoformat() if client.get('created_at') else ''
            ])

        # Prepare response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=global_stats.csv'}
        )

    except Exception as e:
        logger.error(f"Export global stats error: {e}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/client/<client_id>/stats/charts', methods=['GET'])
def get_client_chart_data(client_id: str):
    """Get comprehensive chart data for client dashboard"""
    try:
        savings_trend = execute_query("""
            SELECT
                MONTHNAME(CONCAT(year, '-', LPAD(month, 2, '0'), '-01')) as month,
                savings,
                baseline_cost,
                actual_cost
            FROM client_savings_monthly
            WHERE client_id = %s
            ORDER BY year DESC, month DESC
            LIMIT 12
        """, (client_id,), fetch=True)

        return jsonify({
            'savingsTrend': list(reversed([{
                'month': s['month'],
                'savings': float(s['savings'] or 0),
                'baseline': float(s['baseline_cost'] or 0),
                'actual': float(s['actual_cost'] or 0)
            } for s in (savings_trend or [])]))
        })

    except Exception as e:
        logger.error(f"Get chart data error: {e}")
        return jsonify({'error': str(e)}), 500

# Note: Many analytics endpoints are distributed across other modules:
# - /api/client/<client_id>/agents/decisions - Client agent decision history
# - /api/client/instances/<instance_id>/logs - Instance logs (in instances.py)
# - /api/client/instances/<instance_id>/pool-volatility - Pool volatility (in instances.py)
# - /api/client/instances/<instance_id>/simulate-switch - Switch simulation (in instances.py)
# - /api/agents/<agent_id>/statistics - Agent statistics (in agents.py)
# - /api/admin/pools/statistics - Pool statistics (separate endpoint)
# - /api/admin/agents/health-summary - Agent health summary (separate endpoint)
# - /api/client/<client_id>/analytics/downtime - Downtime analytics (separate endpoint)
# - /api/admin/search - Global search (separate endpoint)
# - /api/admin/bulk/execute - Bulk operations (separate endpoint)
# - /api/client/<client_id>/pricing-alerts - Pricing alerts (separate endpoint)
# - /api/events/stream - Event streaming (separate endpoint)

# Placeholder stubs for remaining analytics endpoints that need full implementation:
# These would require reading additional sections of backend.py for complete implementations
