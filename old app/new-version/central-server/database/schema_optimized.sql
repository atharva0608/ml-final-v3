-- ============================================================================
-- AWS SPOT OPTIMIZER - OPTIMIZED PRODUCTION SCHEMA v7.0
-- ============================================================================
-- Created: 2024-11-27
-- Optimized for: Production deployment with real-time state management
--
-- Key Improvements from v6.0:
-- - Normalized pricing pipeline (staging → consolidated → canonical)
-- - Optimized indexes for common query patterns
-- - Real-time state management (LAUNCHING/TERMINATING)
-- - Comprehensive constraints and foreign keys
-- - Reduced table count (33 → 28 core tables)
-- - Better data types (no oversized VARCHARs)
-- - SSE event tracking
-- - Improved emergency flow handling
-- ============================================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = utf8mb4_unicode_ci;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- CORE ENTITIES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Clients (Organizations/Accounts)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clients (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    client_token CHAR(64) UNIQUE NOT NULL COMMENT 'SHA-256 hash for auth',

    -- Subscription & Limits
    plan ENUM('free', 'basic', 'pro', 'enterprise') DEFAULT 'free',
    max_agents SMALLINT UNSIGNED DEFAULT 5,
    max_instances SMALLINT UNSIGNED DEFAULT 10,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    total_savings DECIMAL(12, 4) DEFAULT 0.0000,

    -- Default Settings
    default_auto_terminate BOOLEAN DEFAULT TRUE,
    default_terminate_wait_seconds SMALLINT UNSIGNED DEFAULT 300,
    default_auto_switch_enabled BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP NULL,

    -- Metadata
    metadata JSON,

    -- Indexes
    INDEX idx_clients_token (client_token),
    INDEX idx_clients_active (is_active, created_at DESC),
    INDEX idx_clients_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Client accounts with subscription tiers';

-- ----------------------------------------------------------------------------
-- Agents (Logical Identity - Persists Across Instance Changes)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agents (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    client_id CHAR(36) NOT NULL,

    -- Persistent Identity
    logical_agent_id VARCHAR(128) NOT NULL COMMENT 'Stable across reinstalls',
    hostname VARCHAR(255),

    -- Current Instance Context
    instance_id VARCHAR(20),
    instance_type VARCHAR(32),
    region VARCHAR(20) NOT NULL,
    az VARCHAR(32),
    ami_id VARCHAR(32),

    -- Network
    private_ip VARCHAR(45),
    public_ip VARCHAR(45),

    -- Current Mode & Pool
    current_mode ENUM('unknown', 'ondemand', 'spot') DEFAULT 'unknown',
    current_pool_id VARCHAR(100),

    -- Pricing Context
    spot_price DECIMAL(10, 6),
    ondemand_price DECIMAL(10, 6),
    baseline_ondemand_price DECIMAL(10, 6),

    -- Agent Configuration
    agent_version VARCHAR(20),
    config_version SMALLINT UNSIGNED DEFAULT 0,
    instance_count SMALLINT UNSIGNED DEFAULT 0,

    -- Status & Health
    status ENUM('offline', 'online', 'error') DEFAULT 'offline',
    enabled BOOLEAN DEFAULT TRUE,
    last_heartbeat_at TIMESTAMP NULL,
    heartbeat_interval_seconds SMALLINT UNSIGNED DEFAULT 30,

    -- Toggles
    auto_switch_enabled BOOLEAN DEFAULT TRUE,
    auto_terminate_enabled BOOLEAN DEFAULT TRUE,
    terminate_wait_seconds SMALLINT UNSIGNED DEFAULT 300,
    replica_enabled BOOLEAN DEFAULT FALSE,
    replica_count TINYINT UNSIGNED DEFAULT 1,
    manual_replica_enabled BOOLEAN DEFAULT FALSE,

    -- Emergency Context
    notice_status ENUM('none', 'rebalance', 'termination') DEFAULT 'none',
    notice_deadline TIMESTAMP NULL,
    fastest_boot_pool_id VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Metadata
    metadata JSON,

    -- Indexes
    INDEX idx_agents_client (client_id, created_at DESC),
    INDEX idx_agents_instance (instance_id),
    INDEX idx_agents_status (status, last_heartbeat_at DESC),
    INDEX idx_agents_region (region, az),
    INDEX idx_agents_enabled (enabled, status),
    UNIQUE KEY uk_agents_logical (client_id, logical_agent_id),

    -- Constraints
    CONSTRAINT fk_agents_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT chk_agents_replica_xor CHECK (
        NOT (auto_switch_enabled = TRUE AND manual_replica_enabled = TRUE)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Agent logical identity with current instance context';

-- ----------------------------------------------------------------------------
-- Agent Configurations (Advanced Settings)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_configs (
    agent_id CHAR(36) PRIMARY KEY,

    -- ML Decision Thresholds
    min_savings_percent DECIMAL(5, 2) DEFAULT 15.00,
    risk_threshold DECIMAL(4, 3) DEFAULT 0.300,
    max_switches_per_week TINYINT UNSIGNED DEFAULT 10,
    min_pool_duration_hours SMALLINT UNSIGNED DEFAULT 2,

    -- Advanced Options
    preferred_azs JSON COMMENT 'Array of preferred availability zones',
    blacklist_pools JSON COMMENT 'Array of blacklisted pool IDs',
    custom_weights JSON COMMENT 'Custom weights for decision algorithm',

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_agent_configs_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Advanced agent configuration settings';

-- ============================================================================
-- INSTANCE MANAGEMENT
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Instances (EC2 Instances with State Machine)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS instances (
    id VARCHAR(20) PRIMARY KEY COMMENT 'EC2 instance ID or temp ID',
    client_id CHAR(36) NOT NULL,
    agent_id CHAR(36),

    -- Instance Details
    instance_type VARCHAR(32) NOT NULL,
    region VARCHAR(20) NOT NULL,
    az VARCHAR(32) NOT NULL,
    ami_id VARCHAR(32),

    -- Current State
    current_mode ENUM('unknown', 'ondemand', 'spot') DEFAULT 'unknown',
    current_pool_id VARCHAR(100),
    spot_price DECIMAL(10, 6),
    ondemand_price DECIMAL(10, 6),
    baseline_ondemand_price DECIMAL(10, 6),

    -- State Machine (PRIMARY/REPLICA/ZOMBIE/TERMINATED)
    is_active BOOLEAN DEFAULT TRUE,
    instance_status ENUM(
        'launching',
        'running_primary',
        'running_replica',
        'promoting',
        'terminating',
        'terminated',
        'zombie'
    ) DEFAULT 'launching',
    is_primary BOOLEAN DEFAULT FALSE,

    -- Lifecycle Timestamps
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    launch_requested_at TIMESTAMP NULL,
    launch_confirmed_at TIMESTAMP NULL,
    launch_duration_seconds SMALLINT UNSIGNED NULL,
    last_switch_at TIMESTAMP NULL,
    last_interruption_signal TIMESTAMP NULL,
    interruption_handled_count SMALLINT UNSIGNED DEFAULT 0,
    last_failover_at TIMESTAMP NULL,
    termination_requested_at TIMESTAMP NULL,
    termination_confirmed_at TIMESTAMP NULL,
    termination_duration_seconds SMALLINT UNSIGNED NULL,
    terminated_at TIMESTAMP NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Optimistic Locking
    version INT UNSIGNED DEFAULT 1,

    -- Metadata
    metadata JSON,

    -- Indexes
    INDEX idx_instances_client (client_id, created_at DESC),
    INDEX idx_instances_agent (agent_id, is_primary, instance_status),
    INDEX idx_instances_type_region (instance_type, region, az),
    INDEX idx_instances_status (instance_status, updated_at DESC),
    INDEX idx_instances_pool (current_pool_id),
    INDEX idx_instances_active (is_active, instance_status),
    INDEX idx_instances_launching (instance_status, launch_requested_at)
        COMMENT 'For monitoring stuck launches',
    INDEX idx_instances_terminating (instance_status, termination_requested_at)
        COMMENT 'For monitoring stuck terminations',

    -- Constraints
    CONSTRAINT fk_instances_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT fk_instances_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE SET NULL,
    CONSTRAINT chk_instances_primary_running CHECK (
        (is_primary = TRUE AND instance_status IN ('running_primary', 'promoting'))
        OR is_primary = FALSE
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='EC2 instances with real-time state tracking';

-- Trigger for optimistic locking
DELIMITER //
CREATE TRIGGER IF NOT EXISTS instances_version_increment
BEFORE UPDATE ON instances
FOR EACH ROW
BEGIN
    SET NEW.version = OLD.version + 1;

    -- Auto-calculate durations
    IF NEW.launch_confirmed_at IS NOT NULL AND OLD.launch_confirmed_at IS NULL THEN
        SET NEW.launch_duration_seconds = TIMESTAMPDIFF(SECOND, NEW.launch_requested_at, NEW.launch_confirmed_at);
    END IF;

    IF NEW.termination_confirmed_at IS NOT NULL AND OLD.termination_confirmed_at IS NULL THEN
        SET NEW.termination_duration_seconds = TIMESTAMPDIFF(SECOND, NEW.termination_requested_at, NEW.termination_confirmed_at);
    END IF;
END//
DELIMITER ;

-- Stored Procedure for Atomic Role Promotion
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS promote_instance_to_primary(
    IN p_instance_id VARCHAR(20),
    IN p_agent_id CHAR(36),
    IN p_expected_version INT UNSIGNED
)
BEGIN
    DECLARE v_affected_rows INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Failed to promote instance to primary';
    END;

    START TRANSACTION;

    -- Demote existing primary to zombie
    UPDATE instances
    SET instance_status = 'zombie',
        is_primary = FALSE,
        terminated_at = NOW()
    WHERE agent_id = p_agent_id
        AND is_primary = TRUE
        AND instance_status = 'running_primary'
        AND id != p_instance_id;

    -- Promote new instance with optimistic lock
    UPDATE instances
    SET instance_status = 'running_primary',
        is_primary = TRUE
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
-- COMMAND & CONTROL
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Commands (Priority-Based Command Queue)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS commands (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    client_id CHAR(36) NOT NULL,
    agent_id CHAR(36) NOT NULL,

    -- Idempotency
    request_id CHAR(36) UNIQUE NOT NULL,

    -- Command Details
    command_type ENUM(
        'switch',
        'LAUNCH_INSTANCE',
        'TERMINATE_INSTANCE',
        'PROMOTE_REPLICA_TO_PRIMARY',
        'APPLY_CONFIG',
        'SELF_DESTRUCT'
    ) NOT NULL,
    target_mode ENUM('ondemand', 'spot', 'pool'),
    target_pool_id VARCHAR(100),
    instance_id VARCHAR(20),

    -- Priority (100=Critical/Immediate, 75=Manual, 50=ML Urgent, 25=ML Normal, 10=Scheduled)
    priority TINYINT UNSIGNED DEFAULT 25,
    terminate_wait_seconds SMALLINT UNSIGNED,

    -- Status
    status ENUM('pending', 'executing', 'completed', 'failed') DEFAULT 'pending',
    success BOOLEAN,
    message TEXT,
    execution_result JSON,

    -- Audit Fields
    user_id CHAR(36) COMMENT 'User who initiated manual commands',
    trigger_type ENUM('manual', 'ml', 'emergency', 'scheduled'),
    pre_state JSON,
    post_state JSON,

    -- Metadata
    metadata JSON,
    created_by VARCHAR(50),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,

    -- Optimistic Locking
    version INT UNSIGNED DEFAULT 1,

    -- Indexes
    INDEX idx_commands_client (client_id, created_at DESC),
    INDEX idx_commands_agent_pending (agent_id, status, priority DESC, created_at ASC)
        COMMENT 'Optimized for pending command polling',
    INDEX idx_commands_type (command_type, created_at DESC),
    INDEX idx_commands_instance (instance_id),
    INDEX idx_commands_status_time (status, created_at DESC),

    -- Constraints
    CONSTRAINT fk_commands_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT fk_commands_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Priority-based command queue with idempotency';

-- Trigger for optimistic locking
DELIMITER //
CREATE TRIGGER IF NOT EXISTS commands_version_increment
BEFORE UPDATE ON commands
FOR EACH ROW
BEGIN
    SET NEW.version = OLD.version + 1;
END//
DELIMITER ;

-- ============================================================================
-- PRICING PIPELINE (3-Tier: Staging → Consolidated → Canonical)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Spot Pools (Pool Metadata)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS spot_pools (
    id VARCHAR(100) PRIMARY KEY COMMENT 'Format: type.region.az',
    pool_name VARCHAR(255),
    instance_type VARCHAR(32) NOT NULL,
    region VARCHAR(20) NOT NULL,
    az VARCHAR(32) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,

    -- Boot Time Metrics (for emergency pool selection)
    avg_boot_time_seconds SMALLINT UNSIGNED,
    boot_sample_count SMALLINT UNSIGNED DEFAULT 0,
    last_boot_time_update TIMESTAMP NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Indexes
    UNIQUE KEY uk_pool_type_region_az (instance_type, region, az),
    INDEX idx_pools_active (is_active, instance_type),
    INDEX idx_pools_boot_time (avg_boot_time_seconds ASC) COMMENT 'For fastest pool selection'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Spot instance pool metadata with boot metrics';

-- ----------------------------------------------------------------------------
-- Tier 1: Spot Price Snapshots (Staging - Raw Data from Agents)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS spot_price_snapshots (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    client_id CHAR(36) NOT NULL,
    agent_id CHAR(36) NOT NULL,
    pool_id VARCHAR(100) NOT NULL,

    price DECIMAL(10, 6) NOT NULL,
    observed_at TIMESTAMP NOT NULL,

    -- Source Context
    source_instance_id VARCHAR(20) COMMENT 'Which instance reported this',
    source_instance_role ENUM('primary', 'replica', 'zombie') COMMENT 'Role at observation time',

    -- Deduplication
    is_duplicate BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    INDEX idx_snapshots_pool_time (pool_id, observed_at DESC),
    INDEX idx_snapshots_agent (agent_id, observed_at DESC),
    INDEX idx_snapshots_dedup (pool_id, observed_at, is_duplicate)
        COMMENT 'For deduplication queries',
    INDEX idx_snapshots_consolidation (created_at, is_duplicate)
        COMMENT 'For consolidation job',

    -- Constraints
    CONSTRAINT fk_snapshots_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT fk_snapshots_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT fk_snapshots_pool FOREIGN KEY (pool_id)
        REFERENCES spot_pools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Raw pricing snapshots from agents (staging layer)'
PARTITION BY RANGE (UNIX_TIMESTAMP(created_at)) (
    PARTITION p_current VALUES LESS THAN (UNIX_TIMESTAMP('2025-01-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- ----------------------------------------------------------------------------
-- Tier 2: Pricing Consolidated (12-Hour Windows, Deduped & Interpolated)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pricing_consolidated (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    pool_id VARCHAR(100) NOT NULL,

    price DECIMAL(10, 6) NOT NULL,
    observed_at TIMESTAMP NOT NULL,

    -- Consolidation Metadata
    is_interpolated BOOLEAN DEFAULT FALSE COMMENT 'Gap-filled data',
    source_count SMALLINT UNSIGNED DEFAULT 1 COMMENT 'Number of snapshots used',

    -- Job Tracking
    consolidation_job_id CHAR(36),
    consolidated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    UNIQUE KEY uk_consolidated_pool_time (pool_id, observed_at),
    INDEX idx_consolidated_time (observed_at DESC),
    INDEX idx_consolidated_interpolated (is_interpolated, observed_at DESC)
        COMMENT 'For UI markers',

    -- Constraints
    CONSTRAINT fk_consolidated_pool FOREIGN KEY (pool_id)
        REFERENCES spot_pools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Consolidated pricing (12-hour windows, deduped & interpolated)';

-- ----------------------------------------------------------------------------
-- Tier 3: Pricing Canonical (Clean Data for ML Training & Charts)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pricing_canonical (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    pool_id VARCHAR(100) NOT NULL,

    price DECIMAL(10, 6) NOT NULL,
    observed_at TIMESTAMP NOT NULL,

    -- Quality Metrics
    confidence_score DECIMAL(3, 2) DEFAULT 1.00 COMMENT 'Data quality score',
    volatility_index DECIMAL(5, 4) COMMENT 'Price volatility indicator',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    UNIQUE KEY uk_canonical_pool_time (pool_id, observed_at),
    INDEX idx_canonical_time (observed_at DESC),
    INDEX idx_canonical_training (pool_id, observed_at ASC)
        COMMENT 'For ML training data extraction',

    -- Constraints
    CONSTRAINT fk_canonical_pool FOREIGN KEY (pool_id)
        REFERENCES spot_pools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Canonical pricing layer for ML training and analytics';

-- ----------------------------------------------------------------------------
-- Consolidation Jobs (Track Background Processing)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consolidation_jobs (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),

    job_type ENUM('pricing', 'metrics', 'logs') DEFAULT 'pricing',
    status ENUM('pending', 'running', 'completed', 'failed') DEFAULT 'pending',

    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,

    records_processed INT UNSIGNED DEFAULT 0,
    errors_encountered INT UNSIGNED DEFAULT 0,
    error_message TEXT,

    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    duration_seconds SMALLINT UNSIGNED,

    -- Indexes
    INDEX idx_jobs_status (status, started_at DESC),
    INDEX idx_jobs_window (window_start, window_end)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Background job tracking for data consolidation';

-- ============================================================================
-- SWITCH & REPLICA MANAGEMENT
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Switches (Instance Switch History with Downtime Tracking)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS switches (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    client_id CHAR(36) NOT NULL,
    agent_id CHAR(36) NOT NULL,
    command_id CHAR(36),

    -- Idempotency
    request_id CHAR(36) UNIQUE,

    -- Old Instance
    old_instance_id VARCHAR(20),
    old_instance_type VARCHAR(32),
    old_region VARCHAR(20),
    old_az VARCHAR(32),
    old_mode ENUM('ondemand', 'spot'),
    old_pool_id VARCHAR(100),
    old_ami_id VARCHAR(32),

    -- New Instance
    new_instance_id VARCHAR(20),
    new_instance_type VARCHAR(32),
    new_region VARCHAR(20),
    new_az VARCHAR(32),
    new_mode ENUM('ondemand', 'spot'),
    new_pool_id VARCHAR(100),
    new_ami_id VARCHAR(32),

    -- Pricing & Savings
    on_demand_price DECIMAL(10, 6),
    old_spot_price DECIMAL(10, 6),
    new_spot_price DECIMAL(10, 6),
    savings_impact DECIMAL(10, 6),

    -- Trigger & Downtime
    event_trigger ENUM('manual', 'ml', 'emergency', 'scheduled'),
    trigger_type ENUM('user', 'ml_model', 'rebalance', 'termination'),
    user_id CHAR(36),
    downtime_seconds SMALLINT UNSIGNED,

    switched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    metadata JSON,

    -- Indexes
    INDEX idx_switches_agent (agent_id, switched_at DESC),
    INDEX idx_switches_client (client_id, switched_at DESC),
    INDEX idx_switches_trigger (event_trigger, switched_at DESC),
    INDEX idx_switches_success (success, switched_at DESC),

    -- Constraints
    CONSTRAINT fk_switches_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT fk_switches_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT fk_switches_command FOREIGN KEY (command_id)
        REFERENCES commands(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Instance switch history with downtime tracking';

-- ----------------------------------------------------------------------------
-- Replica Instances (Manual Replica Management)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS replica_instances (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    client_id CHAR(36) NOT NULL,
    agent_id CHAR(36) NOT NULL,
    command_id CHAR(36),

    -- Idempotency
    request_id CHAR(36) UNIQUE,

    -- Replica Details
    cloud_instance_id VARCHAR(20),
    instance_type VARCHAR(32),
    region VARCHAR(20),
    az VARCHAR(32),
    mode ENUM('ondemand', 'spot'),
    pool_id VARCHAR(100),

    -- Status
    status ENUM('launching', 'running', 'terminating', 'terminated') DEFAULT 'launching',

    -- Lifecycle
    launch_requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    launch_completed_at TIMESTAMP NULL,
    terminated_at TIMESTAMP NULL,

    -- Indexes
    INDEX idx_replicas_agent (agent_id, status, launch_requested_at DESC),
    INDEX idx_replicas_status (status, launch_requested_at DESC),
    INDEX idx_replicas_cloud_id (cloud_instance_id),

    -- Constraints
    CONSTRAINT fk_replicas_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT fk_replicas_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT fk_replicas_command FOREIGN KEY (command_id)
        REFERENCES commands(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Manual replica instance management';

-- ============================================================================
-- ML MODEL & DECISION TRACKING
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ML Models (Model Registry)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ml_models (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),

    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    model_type ENUM('decision_tree', 'random_forest', 'neural_network', 'heuristic') NOT NULL,

    -- Binary Storage
    model_binary LONGBLOB COMMENT 'Serialized model (pickle, ONNX, etc.)',
    model_hash CHAR(64) COMMENT 'SHA-256 for integrity',

    -- Metadata
    training_dataset_id CHAR(36),
    accuracy_score DECIMAL(5, 4),
    precision_score DECIMAL(5, 4),
    recall_score DECIMAL(5, 4),
    f1_score DECIMAL(5, 4),

    -- Status
    is_active BOOLEAN DEFAULT FALSE,
    validation_status ENUM('pending', 'validated', 'failed') DEFAULT 'pending',

    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP NULL,
    uploaded_by CHAR(36),

    metadata JSON,

    -- Indexes
    UNIQUE KEY uk_model_name_version (model_name, model_version),
    INDEX idx_models_active (is_active, activated_at DESC),
    INDEX idx_models_type (model_type, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='ML model registry with versioning';

-- ----------------------------------------------------------------------------
-- ML Decisions (Decision Audit Trail)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ml_decisions (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    client_id CHAR(36) NOT NULL,
    agent_id CHAR(36) NOT NULL,
    model_id CHAR(36),

    -- Decision Context
    current_pool_id VARCHAR(100),
    current_price DECIMAL(10, 6),

    -- Recommendation
    recommended_action ENUM('switch', 'stay', 'emergency_replica') NOT NULL,
    recommended_pool_id VARCHAR(100),
    recommended_price DECIMAL(10, 6),
    expected_savings DECIMAL(10, 6),
    confidence_score DECIMAL(5, 4),
    risk_score DECIMAL(5, 4),

    -- Input Features
    input_features JSON NOT NULL,

    -- Outcome
    action_taken BOOLEAN DEFAULT FALSE,
    command_id CHAR(36),
    actual_savings DECIMAL(10, 6),

    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    INDEX idx_decisions_agent (agent_id, decided_at DESC),
    INDEX idx_decisions_model (model_id, decided_at DESC),
    INDEX idx_decisions_action (recommended_action, action_taken, decided_at DESC),

    -- Constraints
    CONSTRAINT fk_decisions_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT fk_decisions_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT fk_decisions_model FOREIGN KEY (model_id)
        REFERENCES ml_models(id) ON DELETE SET NULL,
    CONSTRAINT fk_decisions_command FOREIGN KEY (command_id)
        REFERENCES commands(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='ML decision audit trail with outcomes';

-- ----------------------------------------------------------------------------
-- ML Training Datasets (Dataset Metadata)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ml_training_datasets (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),

    dataset_name VARCHAR(100) NOT NULL,
    dataset_version VARCHAR(20) NOT NULL,

    -- Data Range
    data_start_date DATE NOT NULL,
    data_end_date DATE NOT NULL,
    record_count INT UNSIGNED,

    -- Quality Metrics
    feature_count SMALLINT UNSIGNED,
    null_percentage DECIMAL(5, 2),
    duplicate_percentage DECIMAL(5, 2),

    -- Storage
    storage_location VARCHAR(500) COMMENT 'S3/local path',
    file_size_mb DECIMAL(10, 2),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by CHAR(36),

    metadata JSON,

    -- Indexes
    UNIQUE KEY uk_dataset_name_version (dataset_name, dataset_version),
    INDEX idx_datasets_date_range (data_start_date, data_end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='ML training dataset metadata';

-- ============================================================================
-- EVENT & AUDIT LOGGING
-- ============================================================================

-- ----------------------------------------------------------------------------
-- System Events (General Event Log)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_events (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    severity ENUM('debug', 'info', 'warning', 'error', 'critical') NOT NULL,
    message TEXT NOT NULL,

    -- Context
    client_id CHAR(36),
    agent_id CHAR(36),
    instance_id VARCHAR(20),

    -- Metadata
    metadata JSON,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    INDEX idx_events_type (event_type, created_at DESC),
    INDEX idx_events_severity (severity, created_at DESC),
    INDEX idx_events_client (client_id, created_at DESC),
    INDEX idx_events_agent (agent_id, created_at DESC),
    INDEX idx_events_time (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='System-wide event log for audit'
PARTITION BY RANGE (UNIX_TIMESTAMP(created_at)) (
    PARTITION p_current VALUES LESS THAN (UNIX_TIMESTAMP('2025-01-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- ----------------------------------------------------------------------------
-- SSE Events (Real-Time Event Delivery Tracking)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sse_events (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    client_id CHAR(36) NOT NULL,

    event_type ENUM(
        'INSTANCE_LAUNCHING',
        'INSTANCE_RUNNING',
        'INSTANCE_TERMINATING',
        'INSTANCE_TERMINATED',
        'AGENT_STATUS_CHANGED',
        'EMERGENCY_EVENT',
        'COMMAND_EXECUTED',
        'HEARTBEAT'
    ) NOT NULL,

    event_data JSON NOT NULL,

    -- Delivery Status
    delivered BOOLEAN DEFAULT FALSE,
    delivered_at TIMESTAMP NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL COMMENT 'Auto-cleanup after 1 hour',

    -- Indexes
    INDEX idx_sse_client_pending (client_id, delivered, created_at ASC)
        COMMENT 'For fetching pending events',
    INDEX idx_sse_cleanup (expires_at ASC)
        COMMENT 'For cleanup job',

    -- Constraints
    CONSTRAINT fk_sse_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='SSE event queue for real-time updates';

-- ============================================================================
-- NOTIFICATIONS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Notifications (User Notifications)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    client_id CHAR(36) NOT NULL,

    message TEXT NOT NULL,
    notification_type ENUM('info', 'success', 'warning', 'error') NOT NULL,

    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP NULL,

    -- Indexes
    INDEX idx_notifications_client_unread (client_id, is_read, created_at DESC),
    INDEX idx_notifications_time (created_at DESC),

    -- Constraints
    CONSTRAINT fk_notifications_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='User notifications';

-- ============================================================================
-- OPERATIONAL VIEWS
-- ============================================================================

-- Agent Health Summary
CREATE OR REPLACE VIEW v_agent_health_summary AS
SELECT
    a.id AS agent_id,
    a.client_id,
    a.status,
    a.last_heartbeat_at,
    TIMESTAMPDIFF(SECOND, a.last_heartbeat_at, NOW()) AS seconds_since_heartbeat,
    a.instance_id,
    a.current_mode,
    a.current_pool_id,
    COUNT(DISTINCT i.id) AS total_instances,
    SUM(CASE WHEN i.is_primary THEN 1 ELSE 0 END) AS primary_count,
    SUM(CASE WHEN i.instance_status = 'running_replica' THEN 1 ELSE 0 END) AS replica_count,
    SUM(CASE WHEN i.instance_status = 'zombie' THEN 1 ELSE 0 END) AS zombie_count
FROM agents a
LEFT JOIN instances i ON i.agent_id = a.id AND i.is_active = TRUE
GROUP BY a.id;

-- Active Instances Summary
CREATE OR REPLACE VIEW v_active_instances_summary AS
SELECT
    i.client_id,
    i.agent_id,
    COUNT(*) AS total_active,
    SUM(CASE WHEN i.is_primary THEN 1 ELSE 0 END) AS primary_count,
    SUM(CASE WHEN i.instance_status = 'running_replica' THEN 1 ELSE 0 END) AS replica_count,
    SUM(CASE WHEN i.current_mode = 'spot' THEN 1 ELSE 0 END) AS spot_count,
    SUM(CASE WHEN i.current_mode = 'ondemand' THEN 1 ELSE 0 END) AS ondemand_count,
    AVG(i.spot_price) AS avg_spot_price,
    AVG(i.ondemand_price) AS avg_ondemand_price,
    SUM(COALESCE(i.ondemand_price, 0) - COALESCE(i.spot_price, 0)) AS total_hourly_savings
FROM instances i
WHERE i.is_active = TRUE
    AND i.instance_status IN ('running_primary', 'running_replica')
GROUP BY i.client_id, i.agent_id;

-- Recent Switches Summary
CREATE OR REPLACE VIEW v_recent_switches_summary AS
SELECT
    s.client_id,
    s.agent_id,
    COUNT(*) AS total_switches_24h,
    SUM(CASE WHEN s.event_trigger = 'manual' THEN 1 ELSE 0 END) AS manual_switches,
    SUM(CASE WHEN s.event_trigger = 'ml' THEN 1 ELSE 0 END) AS ml_switches,
    SUM(CASE WHEN s.event_trigger = 'emergency' THEN 1 ELSE 0 END) AS emergency_switches,
    AVG(s.downtime_seconds) AS avg_downtime_seconds,
    SUM(s.savings_impact) AS total_savings_impact
FROM switches s
WHERE s.switched_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
    AND s.success = TRUE
GROUP BY s.client_id, s.agent_id;

-- ============================================================================
-- CLEANUP AND MAINTENANCE
-- ============================================================================

-- Event to clean up old SSE events
DELIMITER //
CREATE EVENT IF NOT EXISTS cleanup_sse_events
ON SCHEDULE EVERY 1 HOUR
DO
BEGIN
    DELETE FROM sse_events WHERE expires_at < NOW();
END//
DELIMITER ;

-- Event to clean up old system events (keep 90 days)
DELIMITER //
CREATE EVENT IF NOT EXISTS cleanup_old_events
ON SCHEDULE EVERY 1 DAY
DO
BEGIN
    DELETE FROM system_events
    WHERE created_at < DATE_SUB(NOW(), INTERVAL 90 DAY)
    AND severity IN ('debug', 'info');
END//
DELIMITER ;

-- Event to archive old snapshots (move to consolidated)
DELIMITER //
CREATE EVENT IF NOT EXISTS archive_old_snapshots
ON SCHEDULE EVERY 12 HOUR
DO
BEGIN
    -- This would trigger the consolidation job
    -- Actual logic in jobs/pricing_consolidation.py
    INSERT INTO system_events (event_type, severity, message)
    VALUES ('snapshot_archive_triggered', 'info', 'Snapshot archival event fired');
END//
DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
