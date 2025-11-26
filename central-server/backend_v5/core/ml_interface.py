"""
ML Model Interface with Schema Validation.

Provides interface for:
- ML decision engine invocation with input/output validation
- Model registry management
- Decision logging and tracking
- Model performance metrics
"""
import logging
import json
from typing import Dict, Optional, List
from marshmallow import Schema, fields, validates, ValidationError, EXCLUDE
from core.database import execute_query
from core.utils import generate_uuid, log_system_event

logger = logging.getLogger(__name__)


# ============================================================================
# VALIDATION SCHEMAS
# ============================================================================

class PricingWindowSchema(Schema):
    """Schema for pricing time series data."""
    class Meta:
        unknown = EXCLUDE

    pool_id = fields.Str(required=True)
    prices = fields.List(fields.Dict(), required=True)  # List of {timestamp, price, is_interpolated}


class InstanceFeaturesSchema(Schema):
    """Schema for instance feature data."""
    class Meta:
        unknown = EXCLUDE

    current_role = fields.Str(required=True)
    az = fields.Str(required=True)
    instance_type = fields.Str(required=True)
    uptime_hours = fields.Float(required=False)
    cost_delta = fields.Float(required=False)


class GroupConfigSchema(Schema):
    """Schema for agent group configuration."""
    class Meta:
        unknown = EXCLUDE

    auto_switching = fields.Bool(required=True)
    manual_replica = fields.Bool(required=True)
    auto_terminate = fields.Bool(required=True)


class MLDecisionInputSchema(Schema):
    """Complete input schema for ML decision engine."""
    class Meta:
        unknown = EXCLUDE

    agent_id = fields.Str(required=True)
    pricing_windows = fields.List(fields.Nested(PricingWindowSchema), required=True)
    instance_features = fields.Nested(InstanceFeaturesSchema, required=True)
    group_config = fields.Nested(GroupConfigSchema, required=True)


class MLDecisionOutputSchema(Schema):
    """Output schema for ML decision engine."""
    class Meta:
        unknown = EXCLUDE

    action = fields.Str(required=True)
    confidence = fields.Float(required=True)
    reasoning = fields.Str(required=False, allow_none=True)
    target_pool_id = fields.Str(required=False, allow_none=True)

    @validates('action')
    def validate_action(self, value):
        valid_actions = ['STAY', 'SWITCH', 'CREATE_REPLICA', 'NO_ACTION', 'WAIT']
        if not value.startswith('SWITCH_TO_') and value not in valid_actions:
            raise ValidationError(f"Action must be one of {valid_actions} or SWITCH_TO_<pool_id>")

    @validates('confidence')
    def validate_confidence(self, value):
        if not 0 <= value <= 1:
            raise ValidationError("Confidence must be between 0 and 1")


# ============================================================================
# ML DECISION ENGINE INTERFACE
# ============================================================================

def invoke_ml_decision(agent_id: str, input_data: Dict) -> Optional[Dict]:
    """
    Invoke ML decision engine with validation.

    Args:
        agent_id: Agent UUID
        input_data: Input features dict (will be validated)

    Returns:
        Decision dict with action, confidence, reasoning
        None if failed or no model available
    """
    # Validate input
    input_schema = MLDecisionInputSchema()
    try:
        validated_input = input_schema.load(input_data)
    except ValidationError as e:
        logger.error(f"ML input validation failed for agent {agent_id}: {e.messages}")
        log_system_event(
            'ml_input_validation_failed',
            'error',
            f"ML input validation failed: {e.messages}",
            agent_id=agent_id,
            metadata={'validation_errors': e.messages}
        )
        return None

    # Get active model
    model = execute_query("""
        SELECT * FROM ml_models
        WHERE model_type = 'decision_engine'
            AND is_active = TRUE
        ORDER BY activated_at DESC
        LIMIT 1
    """, fetch_one=True)

    if not model:
        logger.warning(f"No active ML decision model found for agent {agent_id}")
        return {
            'action': 'NO_ACTION',
            'confidence': 0.0,
            'reasoning': 'No active ML model available'
        }

    # Invoke model implementation
    try:
        output = _invoke_model_impl(model['id'], model['model_type'], validated_input)
    except Exception as e:
        logger.error(f"ML model invocation failed: {e}")
        log_system_event(
            'ml_invocation_failed',
            'error',
            f"ML model invocation failed: {e}",
            agent_id=agent_id,
            metadata={'model_id': model['id'], 'error': str(e)}
        )
        return None

    # Validate output
    output_schema = MLDecisionOutputSchema()
    try:
        validated_output = output_schema.load(output)
    except ValidationError as e:
        logger.error(f"ML output validation failed: {e.messages}")
        _log_rejected_ml_output(agent_id, model['id'], output, str(e))
        return None

    # Check confidence threshold
    if validated_output['confidence'] < model['confidence_threshold']:
        logger.info(f"ML decision confidence {validated_output['confidence']} "
                   f"below threshold {model['confidence_threshold']}, treating as NO_ACTION")
        validated_output['action'] = 'NO_ACTION'
        validated_output['reasoning'] = (
            f"Confidence {validated_output['confidence']:.2f} below threshold "
            f"{model['confidence_threshold']:.2f}"
        )

    # Log decision
    _log_ml_decision(agent_id, model['id'], validated_input, validated_output)

    return validated_output


def _invoke_model_impl(model_id: str, model_type: str, input_data: Dict) -> Dict:
    """
    Implementation-specific model invocation.

    This is a placeholder that should be overridden based on your ML framework.

    Args:
        model_id: Model UUID
        model_type: Model type string
        input_data: Validated input dict

    Returns:
        Raw model output dict
    """
    # Get model details
    model = execute_query(
        "SELECT * FROM ml_models WHERE id = %s",
        (model_id,),
        fetch_one=True
    )

    if not model:
        raise Exception(f"Model {model_id} not found")

    # TODO: Implement based on model_format
    # Examples:
    #
    # if model['model_format'] == 'python':
    #     # Load Python module and call predict()
    #     import importlib.util
    #     spec = importlib.util.spec_from_file_location("model", model['model_file_path'])
    #     module = importlib.util.module_from_spec(spec)
    #     spec.loader.exec_module(module)
    #     return module.predict(input_data)
    #
    # elif model['model_format'] == 'onnx':
    #     # Load ONNX model and run inference
    #     import onnxruntime as ort
    #     session = ort.InferenceSession(model['model_file_path'])
    #     ...
    #
    # elif model['model_format'] == 'http':
    #     # POST to model serving endpoint
    #     import requests
    #     response = requests.post(model['model_file_path'], json=input_data)
    #     return response.json()

    # Fallback: Simple rule-based decision (for testing)
    logger.warning("Using fallback rule-based decision (no ML model implemented)")

    pricing_windows = input_data['pricing_windows']
    if not pricing_windows:
        return {'action': 'NO_ACTION', 'confidence': 0.5, 'reasoning': 'No pricing data'}

    # Find cheapest pool
    cheapest_pool = None
    cheapest_price = float('inf')

    for window in pricing_windows:
        if window['prices']:
            recent_price = window['prices'][-1]['price']
            if recent_price < cheapest_price:
                cheapest_price = recent_price
                cheapest_pool = window['pool_id']

    if cheapest_pool:
        return {
            'action': f'SWITCH_TO_{cheapest_pool}',
            'confidence': 0.75,
            'reasoning': f'Cheapest pool is {cheapest_pool} at ${cheapest_price:.4f}',
            'target_pool_id': cheapest_pool
        }

    return {'action': 'NO_ACTION', 'confidence': 0.5, 'reasoning': 'No decision'}


def _log_ml_decision(agent_id: str, model_id: str, input_data: Dict, output: Dict):
    """Log ML decision to database."""
    decision_id = generate_uuid()

    try:
        execute_query("""
            INSERT INTO ml_decisions
            (id, agent_id, model_id, input_features, recommended_action,
             confidence_score, reasoning, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            decision_id,
            agent_id,
            model_id,
            json.dumps(input_data),
            output['action'],
            output['confidence'],
            output.get('reasoning')
        ), commit=True)

        logger.debug(f"ML decision {decision_id} logged for agent {agent_id}")

    except Exception as e:
        logger.error(f"Failed to log ML decision: {e}")


def _log_rejected_ml_output(agent_id: str, model_id: str, output: Dict, error: str):
    """Log ML outputs that failed validation."""
    log_system_event(
        'ml_output_rejected',
        'error',
        f"ML model {model_id} produced invalid output: {error}",
        agent_id=agent_id,
        metadata={
            'model_id': model_id,
            'output': output,
            'validation_error': error
        }
    )


def mark_decision_executed(decision_id: str, result: str, success: bool):
    """Mark ML decision as executed with result."""
    execute_query("""
        UPDATE ml_decisions
        SET was_executed = TRUE,
            execution_result = %s,
            execution_success = %s,
            execution_timestamp = NOW()
        WHERE id = %s
    """, (result, success, decision_id), commit=True)

    logger.info(f"ML decision {decision_id} marked as executed: {result}")


# ============================================================================
# MODEL REGISTRY MANAGEMENT
# ============================================================================

def register_ml_model(
    model_name: str,
    model_version: str,
    model_type: str,
    model_file_path: str,
    model_format: str,
    uploaded_by: str,
    accuracy_metrics: Optional[Dict] = None
) -> str:
    """
    Register a new ML model in the registry.

    Args:
        model_name: Model name
        model_version: Version string
        model_type: 'decision_engine', 'price_predictor', or 'risk_scorer'
        model_file_path: Path to model file on disk
        model_format: 'python', 'onnx', 'tensorflow', 'pytorch'
        uploaded_by: User/system that uploaded
        accuracy_metrics: Optional metrics dict

    Returns:
        model_id UUID
    """
    model_id = generate_uuid()

    execute_query("""
        INSERT INTO ml_models
        (id, model_name, model_version, model_type, model_file_path,
         model_format, uploaded_by, accuracy_metrics, uploaded_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """, (
        model_id,
        model_name,
        model_version,
        model_type,
        model_file_path,
        model_format,
        uploaded_by,
        json.dumps(accuracy_metrics) if accuracy_metrics else None
    ), commit=True)

    logger.info(f"ML model registered: {model_name} v{model_version} ({model_id})")

    log_system_event(
        'ml_model_registered',
        'info',
        f"ML model {model_name} v{model_version} registered",
        metadata={
            'model_id': model_id,
            'model_type': model_type,
            'uploaded_by': uploaded_by
        }
    )

    return model_id


def activate_ml_model(model_id: str) -> bool:
    """
    Activate an ML model (deactivates other models of same type).

    Args:
        model_id: Model UUID to activate

    Returns:
        True if successful
    """
    # Get model details
    model = execute_query(
        "SELECT * FROM ml_models WHERE id = %s",
        (model_id,),
        fetch_one=True
    )

    if not model:
        logger.error(f"Model {model_id} not found")
        return False

    try:
        # Deactivate other models of same type
        execute_query("""
            UPDATE ml_models
            SET is_active = FALSE, deactivated_at = NOW()
            WHERE model_type = %s AND is_active = TRUE
        """, (model['model_type'],), commit=True)

        # Activate this model
        execute_query("""
            UPDATE ml_models
            SET is_active = TRUE, activated_at = NOW()
            WHERE id = %s
        """, (model_id,), commit=True)

        logger.info(f"ML model {model_id} activated ({model['model_name']} v{model['model_version']})")

        log_system_event(
            'ml_model_activated',
            'info',
            f"ML model {model['model_name']} v{model['model_version']} activated",
            metadata={'model_id': model_id, 'model_type': model['model_type']}
        )

        return True

    except Exception as e:
        logger.error(f"Failed to activate model {model_id}: {e}")
        return False


def get_active_models() -> List[Dict]:
    """Get all currently active models."""
    return execute_query("""
        SELECT * FROM ml_models
        WHERE is_active = TRUE
        ORDER BY model_type, activated_at DESC
    """, fetch_all=True) or []


def get_model_performance_metrics(model_id: str, days: int = 7) -> Dict:
    """
    Get performance metrics for a model.

    Args:
        model_id: Model UUID
        days: Number of days to analyze

    Returns:
        Dict with performance metrics
    """
    stats = execute_query("""
        SELECT
            COUNT(*) as total_decisions,
            SUM(CASE WHEN was_executed = TRUE THEN 1 ELSE 0 END) as executed_decisions,
            SUM(CASE WHEN execution_success = TRUE THEN 1 ELSE 0 END) as successful_executions,
            AVG(confidence_score) as avg_confidence,
            MIN(confidence_score) as min_confidence,
            MAX(confidence_score) as max_confidence
        FROM ml_decisions
        WHERE model_id = %s
            AND created_at >= NOW() - INTERVAL %s DAY
    """, (model_id, days), fetch_one=True)

    if not stats:
        return {}

    # Calculate execution rate
    execution_rate = 0
    if stats['total_decisions'] > 0:
        execution_rate = stats['executed_decisions'] / stats['total_decisions']

    # Calculate success rate
    success_rate = 0
    if stats['executed_decisions'] > 0:
        success_rate = stats['successful_executions'] / stats['executed_decisions']

    return {
        'total_decisions': stats['total_decisions'] or 0,
        'executed_decisions': stats['executed_decisions'] or 0,
        'successful_executions': stats['successful_executions'] or 0,
        'execution_rate': execution_rate,
        'success_rate': success_rate,
        'avg_confidence': float(stats['avg_confidence']) if stats['avg_confidence'] else 0,
        'min_confidence': float(stats['min_confidence']) if stats['min_confidence'] else 0,
        'max_confidence': float(stats['max_confidence']) if stats['max_confidence'] else 0,
        'days_analyzed': days
    }
