-- ============================================================================
-- Operational Runbook Alignment Migration
-- ============================================================================
-- This migration adds critical features for production-grade operation:
-- - Optimistic locking for concurrency control
-- - Idempotency support with request_id
-- - Emergency flow tracking
-- - Data consolidation pipeline tables
-- - ML model interface tables
-- - Comprehensive audit fields
-- ============================================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- PHASE 1: OPTIMISTIC LOCKING
-- ============================================================================

-- Add version columns for concurrency control
ALTER TABLE instances ADD COLUMN IF NOT EXISTS version INT DEFAULT 1 COMMENT 'Optimistic locking version';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS version INT DEFAULT 1 COMMENT 'Optimistic locking version';
ALTER TABLE commands ADD COLUMN IF NOT EXISTS version INT DEFAULT 1 COMMENT 'Optimistic locking version';

-- Create triggers to auto-increment version
DELIMITER //

DROP TRIGGER IF EXISTS instances_version_increment//
CREATE TRIGGER instances_version_increment
BEFORE UPDATE ON instances
FOR EACH ROW
BEGIN
    SET NEW.version = OLD.version + 1;
END//

DROP TRIGGER IF EXISTS agents_version_increment//
CREATE TRIGGER agents_version_increment
BEFORE UPDATE ON agents
FOR EACH ROW
BEGIN
    SET NEW.version = OLD.version + 1;
END//

DROP TRIGGER IF EXISTS commands_version_increment//
CREATE TRIGGER commands_version_increment
BEFORE UPDATE ON commands
FOR EACH ROW
BEGIN
    SET NEW.version = OLD.version + 1;
END//

DELIMITER ;

-- ============================================================================
-- PHASE 2: IDEMPOTENCY SUPPORT
-- ============================================================================

-- Add request_id for idempotency
ALTER TABLE commands ADD COLUMN IF NOT EXISTS request_id CHAR(36) COMMENT 'Idempotency key for duplicate prevention';
ALTER TABLE switches ADD COLUMN IF NOT EXISTS request_id CHAR(36) COMMENT 'Idempotency key from originating command';
ALTER TABLE replica_instances ADD COLUMN IF NOT EXISTS request_id CHAR(36) COMMENT 'Idempotency key for replica creation';

-- Add unique constraint for request_id (allow NULL for backward compatibility)
CREATE UNIQUE INDEX IF NOT EXISTS idx_commands_request_id_unique ON commands(request_id);
CREATE INDEX IF NOT EXISTS idx_switches_request_id ON switches(request_id);
CREATE INDEX IF NOT EXISTS idx_replica_request_id ON replica_instances(request_id);

-- ============================================================================
-- PHASE 3: COMPREHENSIVE AUDIT FIELDS
-- ============================================================================

-- Add audit fields to commands
ALTER TABLE commands ADD COLUMN IF NOT EXISTS user_id CHAR(36) COMMENT 'User who initiated action (for manual triggers)';
ALTER TABLE commands ADD COLUMN IF NOT EXISTS pre_state JSON COMMENT 'State before action';
ALTER TABLE commands ADD COLUMN IF NOT EXISTS post_state JSON COMMENT 'State after action';
ALTER TABLE commands ADD COLUMN IF NOT EXISTS lifecycle_event_type VARCHAR(50) COMMENT 'Polymorphic event type';

-- Add user tracking to switches
ALTER TABLE switches ADD COLUMN IF NOT EXISTS user_id CHAR(36) COMMENT 'User who triggered switch';

-- ============================================================================
-- PHASE 4: EMERGENCY FLOW TRACKING
-- ============================================================================

-- Add emergency fields to agents
ALTER TABLE agents ADD COLUMN IF NOT EXISTS fastest_boot_pool_id VARCHAR(128) COMMENT 'Cached fastest boot pool for emergency';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS last_emergency_at TIMESTAMP NULL COMMENT 'Last emergency event timestamp';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS notice_status ENUM('none', 'rebalance', 'termination') DEFAULT 'none' COMMENT 'AWS interruption notice status';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS notice_received_at TIMESTAMP NULL COMMENT 'When notice was received';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS notice_deadline TIMESTAMP NULL COMMENT 'Expected termination time';

-- Add to replica_instances
ALTER TABLE replica_instances ADD COLUMN IF NOT EXISTS emergency_creation BOOLEAN DEFAULT FALSE COMMENT 'Created in emergency flow';
ALTER TABLE replica_instances ADD COLUMN IF NOT EXISTS boot_time_seconds INT COMMENT 'Actual boot time for metrics';

-- Create index for emergency queries
CREATE INDEX IF NOT EXISTS idx_agents_notice_status ON agents(notice_status, notice_deadline);
CREATE INDEX IF NOT EXISTS idx_replica_emergency ON replica_instances(agent_id, emergency_creation, created_at DESC);

-- ============================================================================
-- PHASE 5: DATA CONSOLIDATION PIPELINE
-- ============================================================================

-- Add data source tracking to spot_price_snapshots
ALTER TABLE spot_price_snapshots ADD COLUMN IF NOT EXISTS is_interpolated BOOLEAN DEFAULT FALSE COMMENT 'Synthesized via interpolation';
ALTER TABLE spot_price_snapshots ADD COLUMN IF NOT EXISTS is_backfilled BOOLEAN DEFAULT FALSE COMMENT 'Backfilled from cloud API';
ALTER TABLE spot_price_snapshots ADD COLUMN IF NOT EXISTS data_source VARCHAR(50) DEFAULT 'agent' COMMENT 'agent|interpolation|backfill';

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
    INDEX idx_pricing_consolidated_source (data_source),
    INDEX idx_pricing_consolidated_run (consolidation_run_id)
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

    INDEX idx_consolidation_jobs_type_time (job_type, started_at DESC),
    INDEX idx_consolidation_jobs_status (status, started_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Track data consolidation job execution and metrics';

-- ============================================================================
-- PHASE 6: ML MODEL INTERFACE
-- ============================================================================

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

    -- File storage
    model_file_path VARCHAR(512) COMMENT 'Path to model file on disk',
    model_format VARCHAR(50) COMMENT 'python|onnx|tensorflow|pytorch',

    -- Deployment
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP NULL,
    deactivated_at TIMESTAMP NULL,
    uploaded_by VARCHAR(255),

    UNIQUE KEY uk_model_name_version (model_name, model_version),
    INDEX idx_ml_models_active (is_active, model_type),
    INDEX idx_ml_models_type (model_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Registry of ML models for decision making';

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
    execution_success BOOLEAN,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ml_decisions_agent_time (agent_id, created_at DESC),
    INDEX idx_ml_decisions_model (model_id),
    INDEX idx_ml_decisions_executed (was_executed, created_at),
    INDEX idx_ml_decisions_confidence (confidence_score, created_at DESC),

    CONSTRAINT fk_ml_decisions_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT fk_ml_decisions_model FOREIGN KEY (model_id)
        REFERENCES ml_models(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Log of ML model decisions and their execution outcomes';

-- ML training datasets
CREATE TABLE IF NOT EXISTS ml_training_datasets (
    id CHAR(36) PRIMARY KEY,
    dataset_name VARCHAR(255) NOT NULL,
    dataset_version VARCHAR(50) NOT NULL,

    -- Time range
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    -- Metrics
    total_records INT DEFAULT 0,
    feature_count INT DEFAULT 0,

    -- Storage
    dataset_file_path VARCHAR(512),
    dataset_format VARCHAR(50) COMMENT 'csv|parquet|feather',

    -- Metadata
    extraction_query TEXT COMMENT 'SQL query used to extract data',
    feature_list JSON COMMENT 'List of features included',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),

    UNIQUE KEY uk_dataset_name_version (dataset_name, dataset_version),
    INDEX idx_ml_datasets_date_range (start_date, end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Training datasets for ML model development';

-- ============================================================================
-- PHASE 7: INSTANCE ROLE CONSTRAINTS
-- ============================================================================

-- Add role field if not exists (some schemas may already have this)
-- We're using instance_status for role tracking: running_primary, running_replica, zombie, terminated

-- Create stored procedure to enforce PRIMARY uniqueness
DELIMITER //

DROP PROCEDURE IF EXISTS promote_instance_to_primary//
CREATE PROCEDURE promote_instance_to_primary(
    IN p_instance_id VARCHAR(64),
    IN p_agent_id CHAR(36),
    IN p_expected_version INT
)
BEGIN
    DECLARE v_affected_rows INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Failed to promote instance to primary';
    END;

    START TRANSACTION;

    -- First, demote any existing primary for this agent
    UPDATE instances
    SET instance_status = 'zombie',
        is_primary = FALSE,
        terminated_at = NOW()
    WHERE agent_id = p_agent_id
        AND is_primary = TRUE
        AND instance_status = 'running_primary'
        AND id != p_instance_id;

    -- Promote new instance to primary with optimistic lock check
    UPDATE instances
    SET instance_status = 'running_primary',
        is_primary = TRUE,
        version = version + 1
    WHERE id = p_instance_id
        AND agent_id = p_agent_id
        AND version = p_expected_version;

    SET v_affected_rows = ROW_COUNT();

    IF v_affected_rows = 0 THEN
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Optimistic lock conflict or instance not found';
    ELSE
        COMMIT;
    END IF;
END//

DELIMITER ;

-- ============================================================================
-- PHASE 8: OPERATIONAL METRICS VIEWS
-- ============================================================================

-- Create view for agent health summary
CREATE OR REPLACE VIEW v_agent_health_summary AS
SELECT
    a.client_id,
    COUNT(*) as total_agents,
    SUM(CASE WHEN a.status = 'online' THEN 1 ELSE 0 END) as online_agents,
    SUM(CASE WHEN a.status = 'offline' THEN 1 ELSE 0 END) as offline_agents,
    SUM(CASE WHEN a.notice_status != 'none' THEN 1 ELSE 0 END) as agents_with_notices,
    AVG(CASE WHEN a.status = 'online'
        THEN TIMESTAMPDIFF(SECOND, a.last_heartbeat_at, NOW())
        ELSE NULL END) as avg_heartbeat_age_seconds
FROM agents a
WHERE a.enabled = TRUE
GROUP BY a.client_id;

-- Create view for switch performance metrics
CREATE OR REPLACE VIEW v_switch_performance_24h AS
SELECT
    s.client_id,
    COUNT(*) as total_switches,
    SUM(CASE WHEN s.success = TRUE THEN 1 ELSE 0 END) as successful_switches,
    SUM(CASE WHEN s.success = FALSE THEN 1 ELSE 0 END) as failed_switches,
    AVG(s.downtime_seconds) as avg_downtime_seconds,
    STDDEV(s.downtime_seconds) as stddev_downtime_seconds,
    MIN(s.downtime_seconds) as min_downtime_seconds,
    MAX(s.downtime_seconds) as max_downtime_seconds
FROM switches s
WHERE s.timestamp >= NOW() - INTERVAL 24 HOUR
GROUP BY s.client_id;

-- Create view for emergency events summary
CREATE OR REPLACE VIEW v_emergency_events_daily AS
SELECT
    a.client_id,
    DATE(a.last_emergency_at) as event_date,
    COUNT(*) as emergency_event_count,
    SUM(CASE WHEN a.notice_status = 'rebalance' THEN 1 ELSE 0 END) as rebalance_notices,
    SUM(CASE WHEN a.notice_status = 'termination' THEN 1 ELSE 0 END) as termination_notices,
    AVG(a.emergency_replica_count) as avg_emergency_replicas
FROM agents a
WHERE a.last_emergency_at IS NOT NULL
    AND a.last_emergency_at >= CURDATE() - INTERVAL 30 DAY
GROUP BY a.client_id, DATE(a.last_emergency_at);

-- ============================================================================
-- PHASE 9: CLEANUP AND VERIFICATION
-- ============================================================================

-- Add indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_instances_agent_primary ON instances(agent_id, is_primary, instance_status);
CREATE INDEX IF NOT EXISTS idx_agents_client_status ON agents(client_id, status, enabled);
CREATE INDEX IF NOT EXISTS idx_commands_agent_status_priority ON commands(agent_id, status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_switches_client_time_success ON switches(client_id, timestamp DESC, success);

-- Update existing NULL values for new columns
UPDATE agents SET notice_status = 'none' WHERE notice_status IS NULL;
UPDATE spot_price_snapshots SET data_source = 'agent' WHERE data_source IS NULL;
UPDATE spot_price_snapshots SET is_interpolated = FALSE WHERE is_interpolated IS NULL;
UPDATE spot_price_snapshots SET is_backfilled = FALSE WHERE is_backfilled IS NULL;
UPDATE replica_instances SET emergency_creation = FALSE WHERE emergency_creation IS NULL;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- Version: 1.0
-- Applied: 2024-11-26
-- Description: Operational runbook alignment with concurrency control,
--              idempotency, emergency flows, data pipeline, and ML interface
-- ============================================================================
