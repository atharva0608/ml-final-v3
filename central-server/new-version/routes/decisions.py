from flask import Blueprint, request, jsonify
import logging
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import success_response, error_response, format_decimal, generate_uuid, log_system_event, restart_backend, allowed_file, secure_filename
import json
from datetime import datetime
import uuid
import config

logger = logging.getLogger(__name__)
decisions_bp = Blueprint('decisions', __name__)

@decisions_bp.route('/api/admin/decision-engine/upload', methods=['POST'])
def upload_decision_engine():
    """Upload decision engine files"""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400

        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400

        # Ensure decision engine directory exists
        config.DECISION_ENGINE_DIR.mkdir(parents=True, exist_ok=True)

        uploaded_files = []
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)

                # Validate file extension
                if not allowed_file(filename, config.ALLOWED_ENGINE_EXTENSIONS):
                    return jsonify({
                        'error': f'File type not allowed: {filename}. Allowed types: {", ".join(config.ALLOWED_ENGINE_EXTENSIONS)}'
                    }), 400

                # Save file
                file_path = config.DECISION_ENGINE_DIR / filename
                file.save(str(file_path))
                uploaded_files.append(filename)
                logger.info(f"✓ Uploaded decision engine file: {filename}")

        # Reload decision engine
        logger.info("Reloading decision engine after file upload...")
        from core.decision_engine import decision_engine_manager
        success = decision_engine_manager.load_engine()

        if success:
            log_system_event('decision_engine_updated', 'info',
                           f'Decision engine files uploaded and reloaded: {", ".join(uploaded_files)}')

            # Schedule backend restart
            restart_backend(delay_seconds=3)

            return jsonify({
                'success': True,
                'message': 'Decision engine files uploaded successfully. Backend will restart in 3 seconds.',
                'files': uploaded_files,
                'restarting': True,
                'engine_status': {
                    'loaded': decision_engine_manager.models_loaded,
                    'type': decision_engine_manager.engine_type,
                    'version': decision_engine_manager.engine_version
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Files uploaded but failed to reload decision engine',
                'files': uploaded_files
            }), 500

    except Exception as e:
        logger.error(f"Decision engine upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@decisions_bp.route('/api/admin/ml-models/upload', methods=['POST'])
def upload_ml_models():
    """Upload ML model files with versioning (keeps last 2 upload sessions)"""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400

        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400

        # Ensure model directory exists
        config.MODEL_DIR.mkdir(parents=True, exist_ok=True)

        # Step 1: Mark current live session as fallback
        execute_query("""
            UPDATE model_upload_sessions
            SET is_live = FALSE, is_fallback = TRUE
            WHERE is_live = TRUE AND session_type = 'models'
        """)

        # Step 2: Create new upload session
        session_id = str(uuid.uuid4())
        uploaded_files = []
        total_size = 0

        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)

                # Validate file extension
                if not allowed_file(filename, config.ALLOWED_MODEL_EXTENSIONS):
                    return jsonify({
                        'error': f'File type not allowed: {filename}. Allowed types: {", ".join(config.ALLOWED_MODEL_EXTENSIONS)}'
                    }), 400

                # Save file
                file_path = config.MODEL_DIR / filename
                file.save(str(file_path))

                # Track file info
                file_size = file_path.stat().st_size
                uploaded_files.append(filename)
                total_size += file_size
                logger.info(f"✓ Uploaded ML model file: {filename} ({file_size} bytes)")

        # Step 3: Create upload session record
        execute_query("""
            INSERT INTO model_upload_sessions
            (id, session_type, status, is_live, is_fallback, file_count, file_names, total_size_bytes)
            VALUES (%s, 'models', 'uploaded', FALSE, FALSE, %s, %s, %s)
        """, (session_id, len(uploaded_files), json.dumps(uploaded_files), total_size))

        # Step 4: Clean up old sessions (keep only last 2)
        old_sessions = execute_query("""
            SELECT id, file_names
            FROM model_upload_sessions
            WHERE session_type = 'models'
              AND is_live = FALSE
              AND is_fallback = FALSE
            ORDER BY created_at DESC
            LIMIT 100 OFFSET 1
        """, fetch=True)

        if old_sessions:
            for old_session in old_sessions:
                # Delete old files
                try:
                    old_files = json.loads(old_session['file_names']) if old_session.get('file_names') else []
                    for old_file in old_files:
                        old_path = config.MODEL_DIR / old_file
                        if old_path.exists():
                            old_path.unlink()
                            logger.info(f"Deleted old model file: {old_file}")
                except Exception as e:
                    logger.warning(f"Error deleting old files: {e}")

                # Delete session record
                execute_query("DELETE FROM model_upload_sessions WHERE id = %s", (old_session['id'],))

        logger.info(f"✓ Created new upload session: {session_id} with {len(uploaded_files)} files")

        # Return success response (don't auto-reload yet)
        return jsonify({
            'success': True,
            'message': f'Uploaded {len(uploaded_files)} model files. Use the RESTART button to activate.',
            'files': uploaded_files,
            'sessionId': session_id,
            'requiresRestart': True,
            'model_status': {
                'filesUploaded': len(uploaded_files),
                'totalSize': total_size,
                'sessionType': 'pending_activation'
            }
        }), 200

    except Exception as e:
        logger.error(f"ML models upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@decisions_bp.route('/api/admin/ml-models/activate', methods=['POST'])
def activate_ml_models():
    """Activate uploaded models and restart backend with new models"""
    try:
        data = request.get_json() or {}
        session_id = data.get('sessionId')

        if not session_id:
            return jsonify({'error': 'No session ID provided'}), 400

        # Mark session as live
        execute_query("""
            UPDATE model_upload_sessions
            SET is_live = TRUE, status = 'active', activated_at = NOW()
            WHERE id = %s AND session_type = 'models'
        """, (session_id,))

        # Reload decision engine to pick up new models
        logger.info("Activating new models and reloading decision engine...")
        from core.decision_engine import decision_engine_manager
        success = decision_engine_manager.load_engine()

        if success:
            log_system_event('ml_models_activated', 'info',
                           f'New model session activated: {session_id}')

            # Schedule backend restart
            restart_backend(delay_seconds=3)

            return jsonify({
                'success': True,
                'message': 'Models activated successfully. Backend will restart in 3 seconds.',
                'sessionId': session_id,
                'restarting': True,
                'model_status': {
                    'loaded': decision_engine_manager.models_loaded,
                    'type': decision_engine_manager.engine_type
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to load new models',
                'sessionId': session_id
            }), 500

    except Exception as e:
        logger.error(f"Model activation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@decisions_bp.route('/api/admin/ml-models/fallback', methods=['POST'])
def fallback_ml_models():
    """Fallback to previous model version"""
    try:
        # Get current live and fallback sessions
        live_session = execute_query("""
            SELECT id, file_names FROM model_upload_sessions
            WHERE is_live = TRUE AND session_type = 'models'
            LIMIT 1
        """, fetch_one=True)

        fallback_session = execute_query("""
            SELECT id, file_names FROM model_upload_sessions
            WHERE is_fallback = TRUE AND session_type = 'models'
            ORDER BY created_at DESC LIMIT 1
        """, fetch_one=True)

        if not fallback_session:
            return jsonify({'error': 'No fallback version available'}), 404

        # Swap live and fallback
        if live_session:
            execute_query("""
                UPDATE model_upload_sessions
                SET is_live = FALSE, is_fallback = FALSE, status = 'archived'
                WHERE id = %s
            """, (live_session['id'],))

        execute_query("""
            UPDATE model_upload_sessions
            SET is_live = TRUE, is_fallback = FALSE, status = 'active', activated_at = NOW()
            WHERE id = %s
        """, (fallback_session['id'],))

        logger.info(f"✓ Rolled back to fallback session: {fallback_session['id']}")

        # Reload decision engine
        from core.decision_engine import decision_engine_manager
        success = decision_engine_manager.load_engine()

        if success:
            log_system_event('ml_models_rollback', 'warning',
                           f'Rolled back to previous model version: {fallback_session["id"]}')

            # Schedule backend restart
            restart_backend(delay_seconds=3)

            return jsonify({
                'success': True,
                'message': 'Rolled back to previous model version. Backend will restart in 3 seconds.',
                'fallbackSessionId': fallback_session['id'],
                'restarting': True
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to load fallback models'
            }), 500

    except Exception as e:
        logger.error(f"Model fallback error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@decisions_bp.route('/api/admin/ml-models/sessions', methods=['GET'])
def get_model_sessions():
    """Get model upload session history"""
    try:
        sessions = execute_query("""
            SELECT
                id, session_type, status, is_live, is_fallback,
                file_count, file_names, total_size_bytes,
                created_at, activated_at
            FROM model_upload_sessions
            WHERE session_type = 'models'
            ORDER BY created_at DESC
            LIMIT 10
        """, fetch=True)

        result = [{
            'id': s['id'],
            'status': s['status'],
            'isLive': bool(s['is_live']),
            'isFallback': bool(s['is_fallback']),
            'fileCount': s['file_count'],
            'files': json.loads(s['file_names']) if s.get('file_names') else [],
            'totalSize': s['total_size_bytes'],
            'createdAt': s['created_at'].isoformat() if s.get('created_at') else None,
            'activatedAt': s['activated_at'].isoformat() if s.get('activated_at') else None
        } for s in (sessions or [])]

        return jsonify(result)

    except Exception as e:
        logger.error(f"Get model sessions error: {e}")
        return jsonify({'error': str(e)}), 500
