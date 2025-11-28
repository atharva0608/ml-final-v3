"""
Real-time event broadcasting using Server-Sent Events (SSE)

This module provides SSE endpoints for real-time updates to clients.
Events are broadcasted when:
- Instance state changes (LAUNCHING → RUNNING, TERMINATING → TERMINATED)
- Agent status changes
- Emergency events occur
- Commands are executed
"""

from flask import Blueprint, request, Response, stream_with_context
import logging
import json
import time
from datetime import datetime
from typing import Dict, List
from queue import Queue, Empty
from threading import Lock

logger = logging.getLogger(__name__)
events_bp = Blueprint('events', __name__)

# ============================================================================
# EVENT BROADCASTER - In-Memory Event Queue
# ============================================================================

class EventBroadcaster:
    """
    Simple in-memory event broadcaster for SSE.

    In production, this should be replaced with Redis Pub/Sub or similar
    for multi-instance deployments.
    """

    def __init__(self):
        self.listeners = {}  # client_id -> Queue
        self.lock = Lock()

    def add_listener(self, client_id: str) -> Queue:
        """Register a new listener for a client"""
        with self.lock:
            queue = Queue(maxsize=100)
            self.listeners[client_id] = queue
            logger.info(f"SSE listener added for client {client_id}")
            return queue

    def remove_listener(self, client_id: str):
        """Remove a listener"""
        with self.lock:
            if client_id in self.listeners:
                del self.listeners[client_id]
                logger.info(f"SSE listener removed for client {client_id}")

    def broadcast(self, client_id: str, event_type: str, data: Dict):
        """Broadcast event to a specific client"""
        with self.lock:
            if client_id in self.listeners:
                try:
                    event = {
                        'type': event_type,
                        'data': data,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    self.listeners[client_id].put_nowait(event)
                    logger.debug(f"Event broadcasted to {client_id}: {event_type}")
                except:
                    logger.warning(f"Failed to broadcast to {client_id}, queue full")

    def broadcast_to_all(self, event_type: str, data: Dict):
        """Broadcast event to all connected clients"""
        with self.lock:
            for client_id in list(self.listeners.keys()):
                try:
                    event = {
                        'type': event_type,
                        'data': data,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    self.listeners[client_id].put_nowait(event)
                except:
                    pass


# Global broadcaster instance
broadcaster = EventBroadcaster()


# ============================================================================
# HELPER FUNCTIONS - For other routes to broadcast events
# ============================================================================

def broadcast_instance_state_change(client_id: str, instance_id: str,
                                   old_status: str, new_status: str, **kwargs):
    """Broadcast instance state change event"""
    broadcaster.broadcast(client_id, 'INSTANCE_STATE_CHANGED', {
        'instance_id': instance_id,
        'old_status': old_status,
        'new_status': new_status,
        **kwargs
    })


def broadcast_instance_launching(client_id: str, instance_id: str, instance_type: str, **kwargs):
    """Broadcast instance launching event"""
    broadcaster.broadcast(client_id, 'INSTANCE_LAUNCHING', {
        'instance_id': instance_id,
        'instance_type': instance_type,
        'status': 'launching',
        **kwargs
    })


def broadcast_instance_running(client_id: str, instance_id: str, launch_duration_seconds: int = None, **kwargs):
    """Broadcast instance running event"""
    broadcaster.broadcast(client_id, 'INSTANCE_RUNNING', {
        'instance_id': instance_id,
        'status': 'running',
        'launch_duration_seconds': launch_duration_seconds,
        **kwargs
    })


def broadcast_instance_terminating(client_id: str, instance_id: str, **kwargs):
    """Broadcast instance terminating event"""
    broadcaster.broadcast(client_id, 'INSTANCE_TERMINATING', {
        'instance_id': instance_id,
        'status': 'terminating',
        **kwargs
    })


def broadcast_instance_terminated(client_id: str, instance_id: str, termination_duration_seconds: int = None, **kwargs):
    """Broadcast instance terminated event"""
    broadcaster.broadcast(client_id, 'INSTANCE_TERMINATED', {
        'instance_id': instance_id,
        'status': 'terminated',
        'termination_duration_seconds': termination_duration_seconds,
        **kwargs
    })


def broadcast_agent_status_change(client_id: str, agent_id: str, old_status: str, new_status: str):
    """Broadcast agent status change event"""
    broadcaster.broadcast(client_id, 'AGENT_STATUS_CHANGED', {
        'agent_id': agent_id,
        'old_status': old_status,
        'new_status': new_status
    })


def broadcast_emergency_event(client_id: str, event_type: str, agent_id: str, instance_id: str, **kwargs):
    """Broadcast emergency event"""
    broadcaster.broadcast(client_id, 'EMERGENCY_EVENT', {
        'event_type': event_type,
        'agent_id': agent_id,
        'instance_id': instance_id,
        **kwargs
    })


def broadcast_command_executed(client_id: str, command_id: str, command_type: str,
                               status: str, instance_id: str = None, **kwargs):
    """Broadcast command execution result"""
    broadcaster.broadcast(client_id, 'COMMAND_EXECUTED', {
        'command_id': command_id,
        'command_type': command_type,
        'status': status,
        'instance_id': instance_id,
        **kwargs
    })


# ============================================================================
# SSE ENDPOINTS
# ============================================================================

@events_bp.route('/api/events/stream/<client_id>', methods=['GET'])
def event_stream(client_id: str):
    """
    Server-Sent Events endpoint for real-time updates.

    Usage:
        const eventSource = new EventSource('/api/events/stream/<client_id>');
        eventSource.addEventListener('INSTANCE_STATE_CHANGED', (e) => {
            const data = JSON.parse(e.data);
            console.log('Instance state changed:', data);
        });

    Events:
        - INSTANCE_LAUNCHING
        - INSTANCE_RUNNING
        - INSTANCE_TERMINATING
        - INSTANCE_TERMINATED
        - INSTANCE_STATE_CHANGED
        - AGENT_STATUS_CHANGED
        - EMERGENCY_EVENT
        - COMMAND_EXECUTED
        - HEARTBEAT (every 30s)
    """

    def generate():
        """Generate SSE stream"""
        queue = broadcaster.add_listener(client_id)
        last_heartbeat = time.time()

        try:
            logger.info(f"SSE stream opened for client {client_id}")

            # Send initial connection message
            yield f"event: CONNECTED\ndata: {json.dumps({'client_id': client_id, 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            while True:
                # Send heartbeat every 30 seconds
                if time.time() - last_heartbeat > 30:
                    yield f"event: HEARTBEAT\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"
                    last_heartbeat = time.time()

                # Check for events
                try:
                    event = queue.get(timeout=1)
                    event_type = event['type']
                    event_data = {
                        'data': event['data'],
                        'timestamp': event['timestamp']
                    }
                    yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
                except Empty:
                    continue

        except GeneratorExit:
            logger.info(f"SSE stream closed for client {client_id}")
            broadcaster.remove_listener(client_id)
        except Exception as e:
            logger.error(f"SSE stream error for client {client_id}: {e}")
            broadcaster.remove_listener(client_id)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@events_bp.route('/api/events/test/<client_id>', methods=['POST'])
def test_event(client_id: str):
    """Test endpoint to manually trigger an event"""
    data = request.json or {}
    event_type = data.get('event_type', 'TEST_EVENT')
    event_data = data.get('data', {})

    broadcaster.broadcast(client_id, event_type, event_data)

    return {'success': True, 'message': f'Event {event_type} broadcasted to {client_id}'}


@events_bp.route('/api/events/stats', methods=['GET'])
def event_stats():
    """Get SSE connection statistics"""
    with broadcaster.lock:
        return {
            'active_connections': len(broadcaster.listeners),
            'client_ids': list(broadcaster.listeners.keys())
        }
