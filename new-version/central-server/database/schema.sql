-- ============================================================================
-- AWS SPOT OPTIMIZER - PRODUCTION SCHEMA v6.0
-- ============================================================================
-- Complete database schema aligned with operational runbook requirements
--
-- Features:
-- - Three-tier architecture (PRIMARY/REPLICA/ZOMBIE with strict constraints)
-- - Optimistic locking for concurrency control
-- - Idempotency support with request_id tracking
-- - Emergency flow orchestration (rebalance/termination)
-- - Data consolidation pipeline (deduplication, interpolation, backfill)
-- - ML model interface with decision logging
-- - Comprehensive audit trails with pre/post state
-- - Real-time metrics and operational dashboards
-- ============================================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = utf8mb4_unicode_ci;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- CLIENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS clients (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    client_token VARCHAR(255) UNIQUE NOT NULL,

    -- Subscription & Limits
    plan VARCHAR(50) DEFAULT 'free',
    max_agents INT DEFAULT 5,
    max_instances INT DEFAULT 10,

    -- Status & Metrics
    status VARCHAR(20) DEFAULT 'active',
    is_active BOOLEAN DEFAULT TRUE,
    total_savings DECIMAL(15, 4) DEFAULT 0.0000,

    -- Settings
    default_auto_terminate BOOLEAN DEFAULT TRUE,
    default_terminate_wait_seconds INT DEFAULT 300,
    default_auto_switch_enabled BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP NULL,

    -- Metadata
    metadata JSON,

    INDEX idx_clients_token (client_token),
    INDEX idx_clients_status (status),
    INDEX idx_clients_active (is_active),
    INDEX idx_clients_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Client accounts with subscription and settings';

-- ============================================================================
-- AGENTS TABLE (Persistent Logical Identity)
-- ============================================================================
CREATE TABLE IF NOT EXISTS agents (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    client_id CHAR(36) NOT NULL,

    -- Persistent Identity
    logical_agent_id VARCHAR(255) NOT NULL COMMENT 'Persistent across instance switches',
    hostname VARCHAR(255),

    -- Current Instance Context
    instance_id VARCHAR(50),
    instance_type VARCHAR(50),
    region VARCHAR(50),
    az VARCHAR(50),
    ami_id VARCHAR(50),

    -- Network
    private_ip VARCHAR(45),
    public_ip VARCHAR(45),

    -- Current Mode & Pool
    current_mode VARCHAR(20) DEFAULT 'unknown',
    current_pool_id VARCHAR(100),

    -- Pricing Context
    spot_price DECIMAL(10, 6),
    ondemand_price DECIMAL(10, 6),
    baseline_ondemand_price DECIMAL(10, 6),

    -- Agent Metadata
    agent_version VARCHAR(32),
    config_version INT DEFAULT 0 COMMENT 'Config version for forced refresh',
    instance_count INT DEFAULT 0,

    -- Status & Health
    status VARCHAR(20) DEFAULT 'offline',
    enabled BOOLEAN DEFAULT TRUE,
    last_heartbeat_at TIMESTAMP NULL,

    -- Configuration
    auto_switch_enabled BOOLEAN DEFAULT TRUE,
    auto_terminate_enabled BOOLEAN DEFAULT TRUE,
    terminate_wait_seconds INT DEFAULT 300,

    -- Replica Configuration
    replica_enabled BOOLEAN DEFAULT FALSE,
    replica_count INT DEFAULT 0,
    manual_replica_enabled BOOLEAN DEFAULT FALSE COMMENT 'Manual replica mode (mutually exclusive with auto_switch)',
    current_replica_id VARCHAR(255) DEFAULT NULL,

    -- Emergency Flow Tracking (NEW)
    notice_status ENUM('none', 'rebalance', 'termination') DEFAULT 'none' COMMENT 'AWS interruption notice status',
    notice_received_at TIMESTAMP NULL COMMENT 'When notice was received',
    notice_deadline TIMESTAMP NULL COMMENT 'Expected termination deadline',
    fastest_boot_pool_id VARCHAR(128) COMMENT 'Cached fastest boot pool for emergency',
    last_emergency_at TIMESTAMP NULL COMMENT 'Last emergency event',
    emergency_replica_count INT DEFAULT 0 COMMENT 'Count of emergency replicas created',

    -- Timestamps
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_switch_at TIMESTAMP NULL,
    last_interruption_signal TIMESTAMP NULL,
    interruption_handled_count INT DEFAULT 0,
    last_failover_at TIMESTAMP NULL,
    terminated_at TIMESTAMP NULL,
    last_termination_notice_at TIMESTAMP NULL,
    last_rebalance_recommendation_at TIMESTAMP NULL,
    cleanup_enabled BOOLEAN DEFAULT TRUE,
    last_cleanup_at TIMESTAMP NULL,

    -- Optimistic Locking (NEW)
    version INT DEFAULT 1 COMMENT 'Optimistic lock version',

    -- Metadata
    metadata JSON,

    -- Constraints
    UNIQUE KEY uk_client_logical (client_id, logical_agent_id),

    INDEX idx_agents_client (client_id),
    INDEX idx_agents_instance (instance_id),
    INDEX idx_agents_logical (logical_agent_id),
    INDEX idx_agents_status (status),
    INDEX idx_agents_enabled (enabled),
    INDEX idx_agents_heartbeat (last_heartbeat_at),
    INDEX idx_agents_mode (current_mode),
    INDEX idx_agents_pool (current_pool_id),
    INDEX idx_agents_replica (manual_replica_enabled, replica_count),
    INDEX idx_agents_notice_status (notice_status, notice_deadline),
    INDEX idx_agents_client_status (client_id, status, enabled),

    CONSTRAINT fk_agents_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Agent instances with persistent logical identity and emergency tracking';

-- Trigger for optimistic locking
DELIMITER //
CREATE TRIGGER IF NOT EXISTS agents_version_increment
BEFORE UPDATE ON agents
FOR EACH ROW
BEGIN
    SET NEW.version = OLD.version + 1;
END//
DELIMITER ;

-- ============================================================================
-- AGENT CONFIGURATIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_configs (
    agent_id CHAR(36) PRIMARY KEY,

    -- Risk & Savings Thresholds
    min_savings_percent DECIMAL(5, 2) DEFAULT 15.00,
    risk_threshold DECIMAL(3, 2) DEFAULT 0.30,

    -- Switch Limits
    max_switches_per_week INT DEFAULT 10,
    max_switches_per_day INT DEFAULT 3,
    min_pool_duration_hours INT DEFAULT 2,

    -- Custom Configuration
    custom_config JSON,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_agent_configs_updated (updated_at),

    CONSTRAINT fk_agent_configs_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Per-agent configuration for risk and switch limits';

-- ============================================================================
-- COMMANDS TABLE (Priority-Based Queue with Idempotency)
-- ============================================================================
CREATE TABLE IF NOT EXISTS commands (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    client_id CHAR(36) NOT NULL,
    agent_id CHAR(36) NOT NULL,

    -- Idempotency (NEW)
    request_id CHAR(36) COMMENT 'Idempotency key for duplicate prevention',

    -- Command Details
    command_type VARCHAR(50) NOT NULL,
    target_mode VARCHAR(20),
    target_pool_id VARCHAR(100),
    instance_id VARCHAR(50),

    -- Priority (100=Critical, 75=Manual, 50=ML Urgent, 25=ML Normal, 10=Scheduled)
    priority INT DEFAULT 25,
    terminate_wait_seconds INT,

    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    success BOOLEAN,
    message TEXT,
    execution_result JSON,

    -- Audit Fields (NEW)
    user_id CHAR(36) COMMENT 'User who initiated (for manual)',
    trigger_type VARCHAR(20),
    lifecycle_event_type VARCHAR(50) COMMENT 'Polymorphic event type',
    pre_state JSON COMMENT 'State before action',
    post_state JSON COMMENT 'State after action',

    -- Metadata
    metadata JSON,
    created_by VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,

    -- Optimistic Locking (NEW)
    version INT DEFAULT 1,

    -- Indexes
    UNIQUE KEY uk_commands_request_id (request_id),
    INDEX idx_commands_client (client_id),
    INDEX idx_commands_agent (agent_id),
    INDEX idx_commands_status (status),
    INDEX idx_commands_priority (priority DESC),
    INDEX idx_commands_pending (agent_id, status),
    INDEX idx_commands_type (command_type),
    INDEX idx_commands_created (created_at),
    INDEX idx_commands_agent_status_priority (agent_id, status, priority DESC),
    INDEX idx_commands_request_id (request_id),

    CONSTRAINT fk_commands_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT fk_commands_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Priority-based command queue with idempotency support';

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
-- SPOT POOLS
-- ============================================================================
CREATE TABLE IF NOT EXISTS spot_pools (
    id VARCHAR(128) PRIMARY KEY,
    pool_name VARCHAR(255),
    instance_type VARCHAR(64) NOT NULL,
    region VARCHAR(32) NOT NULL,
    az VARCHAR(48) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,

    -- Boot Time Metrics (NEW - for fastest pool selection)
    avg_boot_time_seconds INT COMMENT 'Average boot time for emergency',
    boot_sample_count INT DEFAULT 0 COMMENT 'Number of boot samples',
    last_boot_time_update TIMESTAMP NULL,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_type_region_az (instance_type, region, az),
    INDEX idx_spot_pools_type_region (instance_type, region),
    INDEX idx_spot_pools_az (az),
    INDEX idx_spot_pools_active (is_active),
    INDEX idx_spot_pools_name (pool_name),
    INDEX idx_spot_pools_boot_time (avg_boot_time_seconds ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Spot instance pools with boot time metrics';

-- Auto-generate pool_name trigger
DELIMITER //
CREATE TRIGGER IF NOT EXISTS before_spot_pools_insert
BEFORE INSERT ON spot_pools
FOR EACH ROW
BEGIN
    IF NEW.pool_name IS NULL THEN
        SET NEW.pool_name = CONCAT(NEW.instance_type, ' (', NEW.az, ')');
    END IF;
END//

CREATE TRIGGER IF NOT EXISTS before_spot_pools_update
BEFORE UPDATE ON spot_pools
FOR EACH ROW
BEGIN
    IF NEW.pool_name IS NULL THEN
        SET NEW.pool_name = CONCAT(NEW.instance_type, ' (', NEW.az, ')');
    END IF;
END//
DELIMITER ;

-- ============================================================================
-- PRICING DATA - THREE-TIER ARCHITECTURE
-- ============================================================================

-- TIER 1: Staging/Temporary - Agent Reports (Raw Data)
CREATE TABLE IF NOT EXISTS spot_price_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pool_id VARCHAR(128) NOT NULL,
    price DECIMAL(10, 6) NOT NULL,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Data Source Tracking (NEW)
    data_source VARCHAR(50) DEFAULT 'agent' COMMENT 'agent|interpolation|backfill',
    is_interpolated BOOLEAN DEFAULT FALSE COMMENT 'Synthesized via interpolation',
    is_backfilled BOOLEAN DEFAULT FALSE COMMENT 'Backfilled from cloud API',

    -- Agent Context
    agent_id CHAR(36) COMMENT 'Which agent captured this',
    instance_role VARCHAR(20) COMMENT 'PRIMARY|REPLICA when captured',

    INDEX idx_spot_snapshots_pool_time (pool_id, captured_at DESC),
    INDEX idx_spot_snapshots_captured (captured_at DESC),
    INDEX idx_spot_snapshots_pool (pool_id),
    INDEX idx_spot_snapshots_timeseries (pool_id, recorded_at DESC),
    INDEX idx_spot_snapshots_source (data_source),
    INDEX idx_spot_snapshots_agent (agent_id),

    CONSTRAINT fk_spot_snapshots_pool FOREIGN KEY (pool_id)
        REFERENCES spot_pools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Staging tier - Raw pricing from agents with source tracking';

-- TIER 2: Consolidated - Deduplicated & Cleaned (For Charts)
CREATE TABLE IF NOT EXISTS pricing_consolidated (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pool_id VARCHAR(128) NOT NULL,
    price DECIMAL(10, 6) NOT NULL,
    timestamp TIMESTAMP NOT NULL,

    -- Data Lineage
    data_source ENUM('agent', 'interpolated', 'backfilled') NOT NULL,
    consolidation_run_id CHAR(36) COMMENT 'Batch job run ID',

    -- Quality Markers
    confidence_score DECIMAL(3, 2) DEFAULT 1.00 COMMENT '0-1, lower for interpolated',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_pool_timestamp (pool_id, timestamp),
    INDEX idx_pricing_consolidated_pool_time (pool_id, timestamp DESC),
    INDEX idx_pricing_consolidated_source (data_source),
    INDEX idx_pricing_consolidated_run (consolidation_run_id),
    INDEX idx_pricing_consolidated_recent (pool_id, timestamp DESC, data_source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Consolidated tier - Deduplicated pricing for charts';

-- TIER 3: Canonical - ML Training Data (Primary Layer)
CREATE TABLE IF NOT EXISTS pricing_canonical (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pool_id VARCHAR(128) NOT NULL,
    price DECIMAL(10, 6) NOT NULL,
    timestamp TIMESTAMP NOT NULL,

    -- Lifecycle Context (for ML training)
    associated_instance_id VARCHAR(64),
    notice_status VARCHAR(20) COMMENT 'Was there a notice active?',
    termination_reason VARCHAR(50),

    -- Feature Engineering Fields
    price_volatility DECIMAL(10, 6) COMMENT 'Volatility measure',
    interruption_occurred BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_canonical_pool_timestamp (pool_id, timestamp),
    INDEX idx_pricing_canonical_pool_time (pool_id, timestamp DESC),
    INDEX idx_pricing_canonical_training (pool_id, timestamp DESC, interruption_occurred)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Canonical tier - ML training data with lifecycle features';

-- On-Demand Pricing
CREATE TABLE IF NOT EXISTS ondemand_price_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    region VARCHAR(32) NOT NULL,
    instance_type VARCHAR(64) NOT NULL,
    price DECIMAL(10, 6) NOT NULL,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ondemand_snapshots_type_region_time (instance_type, region, captured_at DESC),
    INDEX idx_ondemand_snapshots_captured (captured_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='On-demand pricing history';

CREATE TABLE IF NOT EXISTS ondemand_prices (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    instance_type VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,
    price DECIMAL(10, 6) NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_type_region (instance_type, region),
    INDEX idx_ondemand_prices_type (instance_type, region)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Current on-demand prices';

CREATE TABLE IF NOT EXISTS spot_prices (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    pool_id VARCHAR(100) NOT NULL,
    instance_type VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,
    az VARCHAR(50) NOT NULL,
    price DECIMAL(10, 6) NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_spot_prices_pool (pool_id),
    INDEX idx_spot_prices_type (instance_type),
    INDEX idx_spot_prices_time (recorded_at DESC),
    INDEX idx_spot_prices_timeseries (pool_id, recorded_at DESC),
    INDEX idx_spot_prices_analysis (instance_type, region, recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Current spot prices';

-- Consolidation Job Tracking
CREATE TABLE IF NOT EXISTS consolidation_jobs (
    id CHAR(36) PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    status ENUM('running', 'completed', 'failed') DEFAULT 'running',

    -- Metrics
    records_processed INT DEFAULT 0,
    duplicates_removed INT DEFAULT 0,
    gaps_interpolated INT DEFAULT 0,
    backfills_added INT DEFAULT 0,

    error_message TEXT,

    INDEX idx_consolidation_jobs_type_time (job_type, started_at DESC),
    INDEX idx_consolidation_jobs_status (status, started_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Data consolidation job execution tracking';

-- ============================================================================
-- PRICING REPORTS (from agents)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pricing_reports (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    agent_id CHAR(36) NOT NULL,

    -- Instance context
    instance_id VARCHAR(50),
    instance_type VARCHAR(50),
    region VARCHAR(50),
    az VARCHAR(50),
    current_mode VARCHAR(20),
    current_pool_id VARCHAR(100),

    -- Pricing summary
    on_demand_price DECIMAL(10, 6),
    current_spot_price DECIMAL(10, 6),
    cheapest_pool_id VARCHAR(100),
    cheapest_pool_price DECIMAL(10, 6),

    -- Full data
    spot_pools JSON,

    -- Timing
    collected_at TIMESTAMP NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_pricing_reports_agent (agent_id),
    INDEX idx_pricing_reports_time (received_at DESC),
    INDEX idx_pricing_reports_instance_type (instance_type),
    INDEX idx_pricing_reports_collected (collected_at DESC),

    CONSTRAINT fk_pricing_reports_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Pricing reports from agents';

-- ============================================================================
-- INSTANCES (Three-Tier State Machine: PRIMARY/REPLICA/ZOMBIE/TERMINATED)
-- ============================================================================
CREATE TABLE IF NOT EXISTS instances (
    id VARCHAR(64) PRIMARY KEY,
    client_id CHAR(36) NOT NULL,
    agent_id CHAR(36),
    instance_type VARCHAR(64) NOT NULL,
    region VARCHAR(32) NOT NULL,
    az VARCHAR(48) NOT NULL,
    ami_id VARCHAR(64),

    -- Current State
    current_mode VARCHAR(20) DEFAULT 'unknown',
    current_pool_id VARCHAR(128),
    spot_price DECIMAL(10, 6),
    ondemand_price DECIMAL(10, 6),
    baseline_ondemand_price DECIMAL(10, 6),

    -- Role in State Machine
    is_active BOOLEAN DEFAULT TRUE,
    instance_status VARCHAR(20) DEFAULT 'launching' COMMENT 'launching|running_primary|running_replica|promoting|terminating|terminated|zombie',
    is_primary BOOLEAN DEFAULT TRUE COMMENT 'TRUE=PRIMARY, FALSE=REPLICA',

    -- Lifecycle Timestamps
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    launch_requested_at TIMESTAMP NULL COMMENT 'When launch command was issued',
    launch_confirmed_at TIMESTAMP NULL COMMENT 'When instance reached running state',
    launch_duration_seconds INT NULL COMMENT 'Time from launch request to running',
    last_switch_at TIMESTAMP NULL,
    last_interruption_signal TIMESTAMP NULL,
    interruption_handled_count INT DEFAULT 0,
    last_failover_at TIMESTAMP NULL,
    termination_requested_at TIMESTAMP NULL COMMENT 'When terminate command was issued',
    termination_confirmed_at TIMESTAMP NULL COMMENT 'When instance reached terminated state',
    termination_duration_seconds INT NULL COMMENT 'Time from termination request to terminated',
    terminated_at TIMESTAMP NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Optimistic Locking (NEW)
    version INT DEFAULT 1,

    -- Metadata
    metadata JSON,

    INDEX idx_instances_client (client_id),
    INDEX idx_instances_agent (agent_id),
    INDEX idx_instances_type_region (instance_type, region),
    INDEX idx_instances_mode (current_mode),
    INDEX idx_instances_active (is_active),
    INDEX idx_instances_pool (current_pool_id),
    INDEX idx_instances_status (instance_status),
    INDEX idx_instances_agent_primary (agent_id, is_primary, instance_status),

    CONSTRAINT fk_instances_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT fk_instances_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Instance lifecycle with PRIMARY/REPLICA/ZOMBIE roles';

-- Trigger for optimistic locking
DELIMITER //
CREATE TRIGGER IF NOT EXISTS instances_version_increment
BEFORE UPDATE ON instances
FOR EACH ROW
BEGIN
    SET NEW.version = OLD.version + 1;
END//

-- Stored Procedure for Atomic Role Promotion
CREATE PROCEDURE IF NOT EXISTS promote_instance_to_primary(
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
-- SWITCH HISTORY (with Downtime Tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS switches (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    client_id CHAR(36) NOT NULL,
    agent_id CHAR(36) NOT NULL,
    command_id CHAR(36),

    -- Idempotency (NEW)
    request_id CHAR(36) COMMENT 'Idempotency key from command',

    -- Old Instance
    old_instance_id VARCHAR(50),
    old_instance_type VARCHAR(50),
    old_region VARCHAR(50),
    old_az VARCHAR(50),
    old_mode VARCHAR(20),
    old_pool_id VARCHAR(100),
    old_ami_id VARCHAR(50),

    -- New Instance
    new_instance_id VARCHAR(50),
    new_instance_type VARCHAR(50),
    new_region VARCHAR(50),
    new_az VARCHAR(50),
    new_mode VARCHAR(20),
    new_pool_id VARCHAR(100),
    new_ami_id VARCHAR(50),

    -- Pricing
    on_demand_price DECIMAL(10, 6),
    old_spot_price DECIMAL(10, 6),
    new_spot_price DECIMAL(10, 6),
    savings_impact DECIMAL(10, 6),

    -- Trigger & Context
    event_trigger VARCHAR(20),
    trigger_type VARCHAR(20),
    user_id CHAR(36) COMMENT 'User who triggered (manual)',

    -- Snapshot Info
    snapshot_used BOOLEAN DEFAULT FALSE,
    snapshot_id VARCHAR(128),
    ami_id VARCHAR(64),

    -- Detailed Timing for Downtime Analysis (NEW)
    initiated_at TIMESTAMP NULL,
    ami_created_at TIMESTAMP NULL,
    instance_launched_at TIMESTAMP NULL,
    instance_ready_at TIMESTAMP NULL,
    old_terminated_at TIMESTAMP NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Duration (in seconds)
    total_duration_seconds INT,
    downtime_seconds INT COMMENT 'Actual downtime for metrics',

    timing_data JSON,

    -- Status
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_switches_client (client_id),
    INDEX idx_switches_agent (agent_id),
    INDEX idx_switches_client_time (client_id, timestamp DESC),
    INDEX idx_switches_time (initiated_at DESC),
    INDEX idx_switches_trigger (event_trigger),
    INDEX idx_switches_instance (old_instance_id),
    INDEX idx_switches_timestamp (timestamp DESC),
    INDEX idx_switches_success (success),
    INDEX idx_switches_client_time_success (client_id, timestamp DESC, success),
    INDEX idx_switches_request_id (request_id),

    CONSTRAINT fk_switches_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT fk_switches_agent FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT fk_switches_command FOREIGN KEY (command_id)
        REFERENCES commands(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Switch history with detailed downtime tracking';

CREATE TABLE IF NOT EXISTS instance_switches (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_id VARCHAR(255) NOT NULL,
    old_instance_id VARCHAR(255),
    new_instance_id VARCHAR(255),
    switch_reason VARCHAR(100),
    switched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    metadata JSON,

    INDEX idx_instance_switches_agent (agent_id, switched_at DESC),
    INDEX idx_instance_switches_time (switched_at DESC),
    INDEX idx_instance_switches_old (old_instance_id),
    INDEX idx_instance_switches_new (new_instance_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Simple switch log for quick queries';

-- ============================================================================
-- REPLICAS (with Emergency Tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS replica_instances (
    id VARCHAR(255) PRIMARY KEY,
    agent_id VARCHAR(255) NOT NULL,
    instance_id VARCHAR(255) NOT NULL,

    replica_type ENUM('manual', 'automatic-rebalance', 'automatic-termination') NOT NULL,
    pool_id VARCHAR(128),
    instance_type VARCHAR(50),
    region VARCHAR(50),
    az VARCHAR(50),

    -- Idempotency (NEW)
    request_id CHAR(36) COMMENT 'Idempotency key',

    -- Emergency Tracking (NEW)
    emergency_creation BOOLEAN DEFAULT FALSE COMMENT 'Created in emergency flow',
    boot_time_seconds INT COMMENT 'Actual boot time for metrics',

    -- Lifecycle
    status ENUM('launching', 'syncing', 'ready', 'promoted', 'terminated', 'failed') NOT NULL DEFAULT 'launching',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    launched_at TIMESTAMP NULL,
    ready_at TIMESTAMP NULL,
    promoted_at TIMESTAMP NULL,
    terminated_at TIMESTAMP NULL,

    -- Metadata
    created_by VARCHAR(255),
    parent_instance_id VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,

    -- Sync Tracking
    sync_status ENUM('initializing', 'syncing', 'synced', 'out-of-sync') DEFAULT 'initializing',
    sync_latency_ms INT,
    last_sync_at TIMESTAMP NULL,
    sync_started_at TIMESTAMP NULL,
    sync_completed_at TIMESTAMP NULL,
    state_transfer_progress DECIMAL(5,2) DEFAULT 0.00,
    error_message TEXT,

    -- Cost
    hourly_cost DECIMAL(10,6),
    total_cost DECIMAL(10,4) DEFAULT 0.0000,
    total_runtime_hours DECIMAL(10, 2) DEFAULT 0,
    accumulated_cost DECIMAL(15, 4) DEFAULT 0,

    -- Interruption
    interruption_signal_type ENUM('rebalance-recommendation', 'termination-notice') DEFAULT NULL,
    interruption_detected_at TIMESTAMP NULL,
    termination_time TIMESTAMP NULL,
    failover_completed_at TIMESTAMP NULL,

    tags JSON,

    INDEX idx_replica_agent_status (agent_id, status),
    INDEX idx_replica_parent (parent_instance_id),
    INDEX idx_replica_created (created_at),
    INDEX idx_replica_active (agent_id, is_active),
    INDEX idx_replica_sync_completed (sync_completed_at),
    INDEX idx_replica_emergency (agent_id, emergency_creation, created_at DESC),
    INDEX idx_replica_request_id (request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Replica instances with emergency flow tracking';

-- ============================================================================
-- ML MODEL INTERFACE
-- ============================================================================

-- ML Models Registry
CREATE TABLE IF NOT EXISTS ml_models (
    id CHAR(36) PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) NOT NULL COMMENT 'decision_engine|price_predictor|risk_scorer',
    is_active BOOLEAN DEFAULT FALSE,

    -- Model Metadata
    training_dataset_id CHAR(36),
    accuracy_metrics JSON,
    confidence_threshold DECIMAL(3, 2) DEFAULT 0.70,

    -- File Storage
    model_file_path VARCHAR(512) COMMENT 'Path to model file',
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
COMMENT='ML model registry for decision making';

-- ML Decision Log
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
    alternative_actions JSON COMMENT 'Other actions with scores',

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
COMMENT='ML decision log with execution outcomes';

-- ML Training Datasets
CREATE TABLE IF NOT EXISTS ml_training_datasets (
    id CHAR(36) PRIMARY KEY,
    dataset_name VARCHAR(255) NOT NULL,
    dataset_version VARCHAR(50) NOT NULL,

    -- Time Range
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    -- Metrics
    total_records INT DEFAULT 0,
    feature_count INT DEFAULT 0,

    -- Storage
    dataset_file_path VARCHAR(512),
    dataset_format VARCHAR(50) COMMENT 'csv|parquet|feather',

    -- Metadata
    extraction_query TEXT COMMENT 'SQL used to extract',
    feature_list JSON,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),

    UNIQUE KEY uk_dataset_name_version (dataset_name, dataset_version),
    INDEX idx_ml_datasets_date_range (start_date, end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Training datasets for ML models';

-- ============================================================================
-- SYSTEM EVENTS & AUDIT
-- ============================================================================
CREATE TABLE IF NOT EXISTS system_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,

    -- Context
    client_id CHAR(36),
    agent_id CHAR(36),

    -- Metadata
    metadata JSON,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_system_events_type (event_type),
    INDEX idx_system_events_severity (severity),
    INDEX idx_system_events_client (client_id, created_at DESC),
    INDEX idx_system_events_agent (agent_id, created_at DESC),
    INDEX idx_system_events_created (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='System-wide event log for audit';

-- ============================================================================
-- NOTIFICATIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    client_id CHAR(36) NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP NULL,

    INDEX idx_notifications_client (client_id, created_at DESC),
    INDEX idx_notifications_unread (client_id, is_read, created_at DESC),

    CONSTRAINT fk_notifications_client FOREIGN KEY (client_id)
        REFERENCES clients(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='User notifications';

-- ============================================================================
-- OPERATIONAL METRICS VIEWS
-- ============================================================================

-- Agent Health Summary
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

-- Switch Performance (24h)
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

-- Emergency Events Summary
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
-- CLEANUP AND INITIALIZATION
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- SCHEMA COMPLETE
-- ============================================================================
-- Version: 6.0
-- Date: 2024-11-26
-- Aligned with: Operational Runbook Requirements
-- Features: Three-tier architecture, optimistic locking, idempotency,
--           emergency flows, data consolidation, ML interface
-- ============================================================================
