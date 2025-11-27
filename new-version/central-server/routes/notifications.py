from flask import Blueprint, request, jsonify
import logging
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import success_response, error_response, format_decimal
import json
from datetime import datetime

logger = logging.getLogger(__name__)
notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/api/notifications', methods=['GET'])
def get_notifications():
    """Get recent notifications"""
    client_id = request.args.get('client_id')
    limit = int(request.args.get('limit', 10))

    try:
        query = """
            SELECT id, message, severity, is_read, created_at
            FROM notifications
        """
        params = []

        if client_id:
            query += " WHERE client_id = %s OR client_id IS NULL"
            params.append(client_id)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        notifications = execute_query(query, tuple(params), fetch=True)

        return jsonify([{
            'id': n['id'],
            'message': n['message'],
            'severity': n['severity'],
            'isRead': n['is_read'],
            'time': n['created_at'].isoformat()
        } for n in notifications or []])
    except Exception as e:
        logger.error(f"Get notifications error: {e}")
        return jsonify({'error': str(e)}), 500

@notifications_bp.route('/api/notifications/<notif_id>/mark-read', methods=['POST'])
def mark_notification_read(notif_id: str):
    """Mark notification as read"""
    try:
        execute_query("""
            UPDATE notifications
            SET is_read = TRUE
            WHERE id = %s
        """, (notif_id,))

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Mark notification read error: {e}")
        return jsonify({'error': str(e)}), 500

@notifications_bp.route('/api/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_read():
    """Mark all notifications as read"""
    data = request.json or {}
    client_id = data.get('client_id')

    try:
        if client_id:
            execute_query("""
                UPDATE notifications
                SET is_read = TRUE
                WHERE client_id = %s OR client_id IS NULL
            """, (client_id,))
        else:
            execute_query("UPDATE notifications SET is_read = TRUE")

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Mark all read error: {e}")
        return jsonify({'error': str(e)}), 500
