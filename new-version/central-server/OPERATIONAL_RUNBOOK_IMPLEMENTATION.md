# Operational Runbook Implementation Plan

## Executive Summary

This document outlines the implementation plan to align the AWS Spot Optimizer backend_v5 with the comprehensive operational runbook requirements. The system manages PRIMARY/REPLICA/ZOMBIE instance lifecycle with ML-driven decision making, emergency handling, and strict consistency guarantees.

## Current State vs Requirements Analysis

### ✅ Already Implemented
- Agent registration with unique ID generation
- Heartbeat processing with inventory reconciliation
- Basic instance lifecycle (PRIMARY/REPLICA/ZOMBIE/TERMINATED statuses)
- Token-based authentication (admin and client)
- Switch history tracking with timing metrics
- Pricing reports from agents
- Basic replica management
- SSE endpoint for real-time UI updates (routes/analytics.py)
- System events logging

### ❌ Critical Gaps to Address

#### 1. Database Schema Issues
- **Missing**: Unique constraint for "exactly one PRIMARY per group"
- **Missing**: Optimistic locking (version columns) for atomic role changes
- **Missing**: request_id column in commands table for idempotency
- **Missing**: Three-tier pricing structure clarity (staging/consolidated/canonical)
- **Missing**: Interpolation/backfill tracking markers
- **Missing**: Mutually exclusive constraint for auto_switch + manual_replica

#### 2. Concurrency & Idempotency
- **Missing**: Optimistic locking implementation for role promotions
- **Missing**: request_id based duplicate prevention
- **Missing**: Atomic transaction guards for state transitions

#### 3. Emergency Flow Orchestration
- **Incomplete**: Rebalance notice → termination notice handling
- **Missing**: Fastest-boot pool selection algorithm
- **Missing**: Emergency replica creation within 2-minute window
- **Missing**: Automatic promotion with health verification

#### 4. Data Pipeline
- **Missing**: 12-hour consolidation job with deduplication
- **Missing**: Gap interpolation algorithm
- **Missing**: 7-day backfill from cloud pricing API
- **Missing**: Distinct visualization for synthesized data

#### 5. ML Model Interface
- **Missing**: Formal input/output schema validation
- **Missing**: Model versioning and A/B testing framework
- **Missing**: Feature extraction for 3-month training data
- **Missing**: Confidence scoring and reasoning capture

#### 6. Audit & Compliance
- **Incomplete**: Pre/post state capture for all actions
- **Missing**: User_id tracking for manual actions
- **Missing**: Comprehensive lifecycle event polymorphism

---

## Implementation Roadmap

### Phase 1: Database Schema Enhancements (Priority: CRITICAL)

#### 1.1 Add Optimistic Locking
```sql
-- Add version columns for concurrency control
ALTER TABLE instances ADD COLUMN version INT DEFAULT 1 COMMENT 'Optimistic locking version';
ALTER TABLE agents ADD COLUMN version INT DEFAULT 1 COMMENT 'Optimistic locking version';
ALTER TABLE commands ADD COLUMN version INT DEFAULT 1 COMMENT 'Optimistic locking version';

-- Create trigger to auto-increment version
DELIMITER //
CREATE TRIGGER instances_version_increment
BEFORE UPDATE ON instances
FOR EACH ROW
BEGIN
    SET NEW.version = OLD.version + 1;
END//
DELIMITER ;
```

#### 1.2 Add PRIMARY Uniqueness Constraint
```sql
-- Add unique constraint for one PRIMARY per agent
CREATE UNIQUE INDEX idx_instances_primary_per_agent
ON instances(agent_id, is_primary)
WHERE is_primary = TRUE AND instance_status IN ('running_primary', 'running');

-- Note: MySQL doesn't support filtered indexes, so we'll enforce in application logic with transaction
```

#### 1.3 Add Idempotency Support
```sql
-- Add request_id to commands table
ALTER TABLE commands ADD COLUMN request_id CHAR(36) UNIQUE COMMENT 'Idempotency key for duplicate prevention';
ALTER TABLE switches ADD COLUMN request_id CHAR(36) COMMENT 'Idempotency key from originating command';
ALTER TABLE replica_instances ADD COLUMN request_id CHAR(36) COMMENT 'Idempotency key for replica creation';

-- Add index for fast lookups
CREATE INDEX idx_commands_request_id ON commands(request_id);
```

#### 1.4 Add Audit Fields
```sql
-- Add comprehensive audit fields
ALTER TABLE commands ADD COLUMN user_id CHAR(36) COMMENT 'User who initiated action (for manual triggers)';
ALTER TABLE commands ADD COLUMN pre_state JSON COMMENT 'State before action';
ALTER TABLE commands ADD COLUMN post_state JSON COMMENT 'State after action';
ALTER TABLE switches ADD COLUMN user_id CHAR(36) COMMENT 'User who triggered switch';

-- Add lifecycle event type
ALTER TABLE commands ADD COLUMN lifecycle_event_type VARCHAR(50) COMMENT 'Polymorphic event type';
```

#### 1.5 Add Emergency Flow Fields
```sql
-- Add emergency flow tracking to agents
ALTER TABLE agents ADD COLUMN fastest_boot_pool_id VARCHAR(128) COMMENT 'Cached fastest boot pool for emergency';
ALTER TABLE agents ADD COLUMN last_emergency_at TIMESTAMP NULL COMMENT 'Last emergency event timestamp';

-- Add notice tracking
ALTER TABLE agents ADD COLUMN notice_status ENUM('none', 'rebalance', 'termination') DEFAULT 'none';
ALTER TABLE agents ADD COLUMN notice_received_at TIMESTAMP NULL;
ALTER TABLE agents ADD COLUMN notice_deadline TIMESTAMP NULL COMMENT 'Expected termination time';

-- Add to replica_instances
ALTER TABLE replica_instances ADD COLUMN emergency_creation BOOLEAN DEFAULT FALSE COMMENT 'Created in emergency flow';
ALTER TABLE replica_instances ADD COLUMN boot_time_seconds INT COMMENT 'Actual boot time for metrics';
```

#### 1.6 Add Data Pipeline Fields
```sql
-- Add to pricing tables
ALTER TABLE spot_price_snapshots ADD COLUMN is_interpolated BOOLEAN DEFAULT FALSE COMMENT 'Synthesized via interpolation';
ALTER TABLE spot_price_snapshots ADD COLUMN is_backfilled BOOLEAN DEFAULT FALSE COMMENT 'Backfilled from cloud API';
ALTER TABLE spot_price_snapshots ADD COLUMN data_source VARCHAR(50) DEFAULT 'agent' COMMENT 'agent|interpolation|backfill';

-- Create consolidated pricing table
CREATE TABLE IF NOT EXISTS pricing_consolidated (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pool_id VARCHAR(128) NOT NULL,
    price DECIMAL(10, 6) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    data_source ENUM('agent', 'interpolated', 'backfilled') NOT NULL,
    consolidation_run_id CHAR(36) COMMENT 'Batch job run ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_pool_timestamp (pool_id, timestamp),
    INDEX idx_pricing_consolidated_pool_time (pool_id, timestamp DESC),
    INDEX idx_pricing_consolidated_source (data_source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Consolidated pricing with deduplication and gap filling';

-- Create consolidation job tracking
CREATE TABLE IF NOT EXISTS consolidation_jobs (
    id CHAR(36) PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    status ENUM('running', 'completed', 'failed') DEFAULT 'running',
    records_processed INT DEFAULT 0,
    duplicates_removed INT DEFAULT 0,
    gaps_interpolated INT DEFAULT 0,
    backfills_added INT DEFAULT 0,
    error_message TEXT,

    INDEX idx_consolidation_jobs_type_time (job_type, started_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

#### 1.7 Add ML Model Interface Tables
```sql
-- ML model registry
CREATE TABLE IF NOT EXISTS ml_models (
    id CHAR(36) PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) NOT NULL COMMENT 'decision_engine|price_predictor|risk_scorer',
    is_active BOOLEAN DEFAULT FALSE,

    -- Model metadata
    training_dataset_id CHAR(36),
    accuracy_metrics JSON,
    confidence_threshold DECIMAL(3, 2) DEFAULT 0.70,

    -- Deployment
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP NULL,
    deactivated_at TIMESTAMP NULL,
    uploaded_by VARCHAR(255),

    UNIQUE KEY uk_model_name_version (model_name, model_version),
    INDEX idx_ml_models_active (is_active, model_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ML decision log
CREATE TABLE IF NOT EXISTS ml_decisions (
    id CHAR(36) PRIMARY KEY,
    agent_id CHAR(36) NOT NULL,
    model_id CHAR(36) NOT NULL,

    -- Input
    input_features JSON NOT NULL,

    -- Output
    recommended_action VARCHAR(50) NOT NULL,
    confidence_score DECIMAL(5, 4) NOT NULL,
    reasoning TEXT,
    alternative_actions JSON COMMENT 'Other considered actions with scores',

    -- Execution
    was_executed BOOLEAN DEFAULT FALSE,
    execution_result VARCHAR(50),
    execution_timestamp TIMESTAMP NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ml_decisions_agent_time (agent_id, created_at DESC),
    INDEX idx_ml_decisions_model (model_id),
    INDEX idx_ml_decisions_executed (was_executed, created_at),

    CONSTRAINT fk_ml_decisions_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT fk_ml_decisions_model FOREIGN KEY (model_id)
        REFERENCES ml_models(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

### Phase 2: Core Backend Updates

#### 2.1 Optimistic Locking Implementation
**File**: `core/database.py`

Add new function:
```python
def execute_with_optimistic_lock(table: str, record_id: str,
                                  update_query: str, params: tuple,
                                  expected_version: int) -> bool:
    """
    Execute update with optimistic locking.

    Returns True if successful, False if version conflict.
    """
    # Append version check to WHERE clause
    versioned_query = f"{update_query} AND version = %s"
    versioned_params = params + (expected_version,)

    affected_rows = execute_query(versioned_query, versioned_params, commit=True)

    if affected_rows == 0:
        # Version conflict - record was modified by another transaction
        logger.warning(f"Optimistic lock conflict for {table} id={record_id}")
        return False

    return True
```

#### 2.2 Idempotency Middleware
**File**: `core/idempotency.py` (NEW)

```python
"""
Idempotency handling for agent commands.
"""
import logging
from functools import wraps
from flask import request, jsonify
from core.database import execute_query
from core.utils import error_response, success_response

logger = logging.getLogger(__name__)

def require_idempotency_key(f):
    """
    Decorator to enforce request_id based idempotency.

    Checks for X-Request-ID header or request_id in JSON body.
    Returns cached response if request already processed.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract request_id
        request_id = request.headers.get('X-Request-ID') or \
                     (request.json or {}).get('request_id')

        if not request_id:
            return jsonify(*error_response(
                "Missing request_id for idempotency",
                "MISSING_REQUEST_ID",
                400
            ))

        # Check if already processed
        existing = execute_query(
            "SELECT status, execution_result FROM commands WHERE request_id = %s",
            (request_id,),
            fetch_one=True
        )

        if existing:
            if existing['status'] == 'completed':
                logger.info(f"Returning cached response for request_id={request_id}")
                return jsonify(success_response(existing['execution_result']))
            elif existing['status'] == 'failed':
                return jsonify(*error_response(
                    "Previous execution failed",
                    "IDEMPOTENT_FAILURE",
                    500
                ))
            else:
                # Still processing
                return jsonify(*error_response(
                    "Request already in progress",
                    "DUPLICATE_REQUEST",
                    409
                ))

        # Store request_id in request context
        request.request_id = request_id

        return f(*args, **kwargs)

    return decorated_function
```

#### 2.3 Emergency Flow Orchestration
**File**: `core/emergency.py` (NEW)

```python
"""
Emergency flow orchestration for rebalance and termination notices.
"""
import logging
from datetime import datetime, timedelta
from core.database import execute_query
from core.utils import log_system_event, create_notification

logger = logging.getLogger(__name__)

def handle_rebalance_notice(agent_id: str, notice_time: datetime):
    """
    Handle AWS rebalance recommendation (best case: 2-minute window).

    Actions:
    1. Mark agent with rebalance status
    2. Create emergency replica in fastest-boot pool
    3. Monitor for termination notice or completion
    """
    logger.warning(f"Rebalance notice received for agent {agent_id}")

    # Update agent notice status
    execute_query("""
        UPDATE agents
        SET notice_status = 'rebalance',
            notice_received_at = %s,
            notice_deadline = %s,
            last_rebalance_recommendation_at = NOW()
        WHERE id = %s
    """, (notice_time, notice_time + timedelta(minutes=2), agent_id), commit=True)

    # Get agent details
    agent = execute_query(
        "SELECT * FROM agents WHERE id = %s",
        (agent_id,),
        fetch_one=True
    )

    # Create emergency replica
    from core.replica import create_emergency_replica
    replica_id = create_emergency_replica(
        agent_id=agent_id,
        reason='rebalance-notice',
        deadline_seconds=120
    )

    log_system_event(
        'rebalance_notice',
        'warning',
        f"Rebalance notice for agent {agent['logical_agent_id']}, emergency replica {replica_id} created",
        client_id=agent['client_id'],
        agent_id=agent_id,
        metadata={'replica_id': replica_id, 'deadline': '120s'}
    )

    return replica_id

def handle_termination_notice(agent_id: str, termination_time: datetime):
    """
    Handle AWS termination notice (worst case: immediate).

    Actions:
    1. Mark agent with termination status
    2. Create emergency replica if not exists
    3. Initiate immediate promotion
    """
    logger.critical(f"Termination notice received for agent {agent_id}")

    # Update agent notice status
    execute_query("""
        UPDATE agents
        SET notice_status = 'termination',
            notice_received_at = NOW(),
            notice_deadline = %s,
            last_termination_notice_at = NOW()
        WHERE id = %s
    """, (termination_time, agent_id), commit=True)

    # Check for existing replica
    replica = execute_query("""
        SELECT id, status FROM replica_instances
        WHERE agent_id = %s AND status IN ('ready', 'syncing', 'launching')
        ORDER BY created_at DESC LIMIT 1
    """, (agent_id,), fetch_one=True)

    if not replica:
        # Create emergency replica
        from core.replica import create_emergency_replica
        replica_id = create_emergency_replica(
            agent_id=agent_id,
            reason='termination-notice',
            deadline_seconds=60  # Even faster
        )
    else:
        replica_id = replica['id']

    # If replica is ready, promote immediately
    if replica and replica['status'] == 'ready':
        from core.replica import promote_replica
        promote_replica(replica_id, emergency=True)

    return replica_id

def select_fastest_boot_pool(agent_id: str, region: str, instance_type: str):
    """
    Select the pool with historically fastest boot time for emergency.

    Returns pool_id with best boot time metrics.
    """
    # Query historical boot times by pool
    pool_stats = execute_query("""
        SELECT
            pool_id,
            AVG(boot_time_seconds) as avg_boot_time,
            COUNT(*) as sample_count
        FROM replica_instances
        WHERE region = %s
            AND instance_type = %s
            AND boot_time_seconds IS NOT NULL
            AND status = 'promoted'
        GROUP BY pool_id
        HAVING sample_count >= 3
        ORDER BY avg_boot_time ASC
        LIMIT 1
    """, (region, instance_type), fetch_one=True)

    if pool_stats:
        logger.info(f"Fastest boot pool: {pool_stats['pool_id']} ({pool_stats['avg_boot_time']}s avg)")
        return pool_stats['pool_id']

    # Fallback: return current pool or any available
    agent = execute_query("SELECT current_pool_id FROM agents WHERE id = %s", (agent_id,), fetch_one=True)
    return agent['current_pool_id'] if agent else None
```

#### 2.4 Data Consolidation Pipeline
**File**: `jobs/pricing_consolidation.py` (NEW)

```python
"""
12-hour data consolidation job with deduplication, interpolation, and backfill.
"""
import logging
from datetime import datetime, timedelta
from core.database import execute_query
from core.utils import generate_uuid

logger = logging.getLogger(__name__)

def run_consolidation_job():
    """
    Main consolidation job - runs every 12 hours.

    Steps:
    1. Deduplicate pricing from agents (PRIMARY takes precedence)
    2. Identify gaps in timeseries
    3. Interpolate missing points
    4. Integrate backfilled data from cloud API
    5. Write to consolidated table
    """
    job_id = generate_uuid()

    execute_query("""
        INSERT INTO consolidation_jobs (id, job_type, started_at, status)
        VALUES (%s, 'pricing_12h', NOW(), 'running')
    """, (job_id,), commit=True)

    try:
        # Step 1: Deduplicate
        duplicates_removed = deduplicate_pricing_snapshots()

        # Step 2 & 3: Interpolate gaps
        gaps_filled = interpolate_pricing_gaps()

        # Step 4: Integrate backfills
        backfills_added = integrate_backfilled_data()

        # Mark job complete
        execute_query("""
            UPDATE consolidation_jobs
            SET status = 'completed',
                completed_at = NOW(),
                duplicates_removed = %s,
                gaps_interpolated = %s,
                backfills_added = %s
            WHERE id = %s
        """, (duplicates_removed, gaps_filled, backfills_added, job_id), commit=True)

        logger.info(f"Consolidation job {job_id} completed: "
                   f"{duplicates_removed} dupes, {gaps_filled} gaps, {backfills_added} backfills")

    except Exception as e:
        logger.error(f"Consolidation job {job_id} failed: {e}")
        execute_query("""
            UPDATE consolidation_jobs
            SET status = 'failed', error_message = %s, completed_at = NOW()
            WHERE id = %s
        """, (str(e), job_id), commit=True)

def deduplicate_pricing_snapshots():
    """
    Remove duplicate pricing from PRIMARY and REPLICA captures.
    Use median if multiple values for same pool+timestamp.
    """
    # Implementation: Find duplicates and apply median strategy
    pass

def interpolate_pricing_gaps():
    """
    Fill gaps in timeseries using linear interpolation.
    Mark records as is_interpolated=true.
    """
    # Implementation: Detect gaps > 5 minutes, interpolate
    pass

def integrate_backfilled_data():
    """
    Integrate 7-day backfill from cloud pricing API.
    Only fill where no agent data exists.
    """
    # Implementation: Merge backfill data with is_backfilled=true
    pass
```

---

### Phase 3: API Endpoint Updates

#### 3.1 Update Agent Endpoints with Idempotency
**Files**: All routes in `routes/agents.py`, `routes/commands.py`, `routes/instances.py`

Add decorator:
```python
from core.idempotency import require_idempotency_key

@agents_bp.route('/api/agents/<agent_id>/issue-switch-command', methods=['POST'])
@require_client_auth
@require_idempotency_key  # NEW
def issue_switch_command(agent_id, authenticated_client_id=None):
    # Implementation with request.request_id
    pass
```

#### 3.2 Add Emergency Notice Endpoints
**File**: `routes/agents.py`

```python
@agents_bp.route('/api/agents/<agent_id>/rebalance-notice', methods=['POST'])
@require_client_auth
def report_rebalance_notice(agent_id, authenticated_client_id=None):
    """Agent reports AWS rebalance recommendation."""
    from core.emergency import handle_rebalance_notice

    data = request.json
    notice_time = datetime.fromisoformat(data['notice_time'])

    replica_id = handle_rebalance_notice(agent_id, notice_time)

    return jsonify(success_response({
        'status': 'acknowledged',
        'emergency_replica_id': replica_id,
        'action': 'emergency_replica_created'
    }))

@agents_bp.route('/api/agents/<agent_id>/termination-notice', methods=['POST'])
@require_client_auth
def report_termination_notice(agent_id, authenticated_client_id=None):
    """Agent reports AWS termination notice."""
    from core.emergency import handle_termination_notice

    data = request.json
    termination_time = datetime.fromisoformat(data['termination_time'])

    replica_id = handle_termination_notice(agent_id, termination_time)

    return jsonify(success_response({
        'status': 'acknowledged',
        'emergency_replica_id': replica_id,
        'action': 'emergency_promotion_initiated'
    }))
```

---

### Phase 4: ML Model Interface

#### 4.1 ML Decision Engine Interface
**File**: `core/ml_interface.py` (NEW)

```python
"""
ML model interface with schema validation.
"""
import logging
import json
from marshmallow import Schema, fields, validates, ValidationError
from core.database import execute_query

logger = logging.getLogger(__name__)

class MLDecisionInputSchema(Schema):
    """Input schema for ML decision engine."""
    agent_id = fields.Str(required=True)
    pricing_windows = fields.Dict(required=True)  # pool_id -> timeseries
    instance_features = fields.Dict(required=True)
    group_config = fields.Dict(required=True)

class MLDecisionOutputSchema(Schema):
    """Output schema for ML decision engine."""
    action = fields.Str(required=True)
    confidence = fields.Float(required=True)
    reasoning = fields.Str(required=False, allow_none=True)

def invoke_ml_decision(agent_id: str, input_data: dict) -> dict:
    """
    Invoke ML decision engine with validation.

    Returns decision with confidence and reasoning.
    """
    # Validate input
    input_schema = MLDecisionInputSchema()
    try:
        validated_input = input_schema.load(input_data)
    except ValidationError as e:
        logger.error(f"ML input validation failed: {e.messages}")
        raise

    # Get active model
    model = execute_query("""
        SELECT * FROM ml_models
        WHERE model_type = 'decision_engine' AND is_active = TRUE
        LIMIT 1
    """, fetch_one=True)

    if not model:
        logger.warning("No active ML decision model found")
        return {'action': 'NO_ACTION', 'confidence': 0.0, 'reasoning': 'No model available'}

    # Invoke model (implementation depends on model format - Python module, REST API, etc.)
    output = _invoke_model_impl(model['id'], validated_input)

    # Validate output
    output_schema = MLDecisionOutputSchema()
    try:
        validated_output = output_schema.load(output)
    except ValidationError as e:
        logger.error(f"ML output validation failed: {e.messages}")
        # Log rejected output for debugging
        log_rejected_ml_output(agent_id, model['id'], output, str(e))
        raise

    # Log decision
    from core.utils import generate_uuid
    decision_id = generate_uuid()
    execute_query("""
        INSERT INTO ml_decisions
        (id, agent_id, model_id, input_features, recommended_action,
         confidence_score, reasoning, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    """, (
        decision_id,
        agent_id,
        model['id'],
        json.dumps(validated_input),
        validated_output['action'],
        validated_output['confidence'],
        validated_output.get('reasoning')
    ), commit=True)

    return validated_output

def _invoke_model_impl(model_id: str, input_data: dict) -> dict:
    """
    Implementation-specific model invocation.
    Override this based on your ML framework.
    """
    # Example: Load Python module and call predict()
    # Example: POST to model serving endpoint
    # Example: Load ONNX model and run inference
    pass

def log_rejected_ml_output(agent_id: str, model_id: str, output: dict, error: str):
    """Log ML outputs that failed validation for debugging."""
    from core.utils import log_system_event
    log_system_event(
        'ml_output_rejected',
        'error',
        f"ML model {model_id} produced invalid output: {error}",
        agent_id=agent_id,
        metadata={'output': output, 'validation_error': error}
    )
```

---

### Phase 5: Monitoring & Metrics

#### 5.1 Operational Metrics Endpoints
**File**: `routes/analytics.py` (ADD)

```python
@analytics_bp.route('/api/admin/metrics/operational', methods=['GET'])
@require_admin_auth
def get_operational_metrics():
    """Get operational metrics dashboard."""

    # Agent uptime percentage
    agent_uptime = execute_query("""
        SELECT
            COUNT(*) as total_agents,
            SUM(CASE WHEN status = 'online' THEN 1 ELSE 0 END) as online_agents,
            (SUM(CASE WHEN status = 'online' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as uptime_percentage
        FROM agents
        WHERE enabled = TRUE
    """, fetch_one=True)

    # Average switch downtime (24-hour rolling)
    switch_downtime = execute_query("""
        SELECT
            AVG(downtime_seconds) as avg_downtime_seconds,
            STDDEV(downtime_seconds) as stddev_downtime_seconds,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY downtime_seconds) as p95_downtime_seconds
        FROM switches
        WHERE timestamp >= NOW() - INTERVAL 24 HOUR
            AND success = TRUE
    """, fetch_one=True)

    # Savings percentage
    savings = execute_query("""
        SELECT
            SUM(total_savings) as total_savings,
            SUM(baseline_ondemand_price * instance_count) as baseline_cost,
            (SUM(total_savings) * 100.0 / SUM(baseline_ondemand_price * instance_count)) as savings_percentage
        FROM clients
        WHERE is_active = TRUE
    """, fetch_one=True)

    # Emergency promotion counts
    emergency_stats = execute_query("""
        SELECT
            COUNT(*) as total_emergency_events,
            SUM(CASE WHEN notice_status = 'rebalance' THEN 1 ELSE 0 END) as rebalance_count,
            SUM(CASE WHEN notice_status = 'termination' THEN 1 ELSE 0 END) as termination_count
        FROM agents
        WHERE last_emergency_at >= CURDATE()
    """, fetch_one=True)

    # Data cleaner metrics
    cleaner_metrics = execute_query("""
        SELECT
            SUM(duplicates_removed) as total_duplicates_removed,
            SUM(gaps_interpolated) as total_gaps_interpolated,
            SUM(backfills_added) as total_backfills_added,
            MAX(completed_at) as last_run_at
        FROM consolidation_jobs
        WHERE status = 'completed'
            AND started_at >= NOW() - INTERVAL 7 DAY
    """, fetch_one=True)

    return jsonify(success_response({
        'agent_uptime': agent_uptime,
        'switch_downtime': switch_downtime,
        'savings': savings,
        'emergency_stats': emergency_stats,
        'data_cleaner': cleaner_metrics
    }))
```

---

## Success Criteria Tracking

| Criterion | Target | Current Status | Notes |
|-----------|--------|----------------|-------|
| Agent heartbeat miss rate | <5% | TBD | Need monitoring |
| Manual switch downtime (p95) | <10s | TBD | Tracked in switches table |
| Emergency promotion window | 99% within 2min | ❌ Not impl | Phase 2 |
| Pricing chart update latency | <30s | ❌ Not impl | Phase 4 |
| ML decision latency | <500ms | ❌ Not impl | Phase 4 |
| Zombie cleanup | 30-day auto | ❌ Not impl | Need scheduled job |

---

## Next Steps

1. **Review and approve** this implementation plan
2. **Execute Phase 1** database migrations (test on staging first!)
3. **Implement Phase 2** core backend changes
4. **Update Phase 3** API endpoints with new features
5. **Deploy Phase 4** ML interface incrementally
6. **Monitor Phase 5** metrics and tune thresholds

---

**Document Version**: 1.0
**Last Updated**: 2024-11-26
**Status**: PENDING APPROVAL
