-- ==============================================================================
-- CloudOptim Core Platform - Database Migration 002
-- Add Customer Feedback Loop and Safety Constraint Enforcement Tables
-- ==============================================================================
-- Purpose: Enable ML learning from real interruptions and enforce safety constraints
-- Author: Claude/Architecture Team
-- Date: 2025-12-01
-- Dependencies: 001_initial_schema.sql (customers, clusters, nodes, spot_events tables)
-- ==============================================================================

-- ==============================================================================
-- TABLE 1: interruption_feedback
-- ==============================================================================
-- Purpose: Track every Spot interruption with rich metadata for ML learning
-- Key Feature: Enables customer feedback loop (0% → 25% weight over 12 months)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS interruption_feedback (
    -- Primary identification
    interruption_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES clusters(cluster_id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,

    -- Instance details
    instance_id VARCHAR(50) NOT NULL,
    instance_type VARCHAR(50) NOT NULL,
    availability_zone VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,

    -- Workload classification (NEW - Critical for pattern detection)
    workload_type VARCHAR(100), -- web, database, ml, batch, streaming, etc.
    pod_name VARCHAR(255),
    namespace VARCHAR(100),

    -- Temporal data (for pattern detection)
    interruption_time TIMESTAMP NOT NULL,
    day_of_week INTEGER NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6), -- 0=Sunday, 6=Saturday
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day >= 0 AND hour_of_day <= 23),
    month_of_year INTEGER NOT NULL CHECK (month_of_year >= 1 AND month_of_year <= 12),

    -- ML prediction accuracy tracking
    was_predicted BOOLEAN NOT NULL DEFAULT false, -- Did ML model predict this interruption?
    risk_score_at_deployment DECIMAL(5,4) CHECK (risk_score_at_deployment >= 0 AND risk_score_at_deployment <= 1),

    -- Recovery metrics
    drain_started_at TIMESTAMP,
    drain_completed_at TIMESTAMP,
    replacement_ready_at TIMESTAMP,
    total_recovery_seconds INTEGER, -- Calculated: replacement_ready - interruption_time

    -- Impact assessment
    customer_impact VARCHAR(50) CHECK (customer_impact IN ('none', 'minimal', 'moderate', 'severe')),
    workload_disrupted BOOLEAN DEFAULT false,
    data_loss_occurred BOOLEAN DEFAULT false,

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for high-performance queries
CREATE INDEX idx_feedback_instance_region ON interruption_feedback(instance_type, region, availability_zone);
CREATE INDEX idx_feedback_temporal ON interruption_feedback(day_of_week, hour_of_day);
CREATE INDEX idx_feedback_workload ON interruption_feedback(workload_type);
CREATE INDEX idx_feedback_customer ON interruption_feedback(customer_id, interruption_time DESC);
CREATE INDEX idx_feedback_cluster ON interruption_feedback(cluster_id, interruption_time DESC);
CREATE INDEX idx_feedback_risk_score ON interruption_feedback(risk_score_at_deployment);

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_interruption_feedback_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_interruption_feedback_timestamp
    BEFORE UPDATE ON interruption_feedback
    FOR EACH ROW
    EXECUTE FUNCTION update_interruption_feedback_timestamp();

COMMENT ON TABLE interruption_feedback IS 'Tracks every Spot interruption for ML learning - enables customer feedback loop (0% → 25% weight)';
COMMENT ON COLUMN interruption_feedback.workload_type IS 'Workload classification for pattern detection (web, database, ml, batch)';
COMMENT ON COLUMN interruption_feedback.was_predicted IS 'Whether ML model predicted this interruption (risk score < 0.80)';
COMMENT ON COLUMN interruption_feedback.customer_impact IS 'Business impact severity: none, minimal, moderate, severe';

-- ==============================================================================
-- TABLE 2: pool_allocations
-- ==============================================================================
-- Purpose: Track current Spot pool allocations to enforce 20% max per pool constraint
-- Key Feature: Prevents concentration risk (max 20% of cluster in single pool)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS pool_allocations (
    -- Primary identification
    allocation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES clusters(cluster_id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,

    -- Pool identification (instance_type:availability_zone)
    pool_key VARCHAR(255) NOT NULL, -- Format: "m5.large:us-east-1a"
    instance_type VARCHAR(50) NOT NULL,
    availability_zone VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,

    -- Allocation tracking
    current_instance_count INTEGER NOT NULL DEFAULT 0 CHECK (current_instance_count >= 0),
    max_instance_count INTEGER NOT NULL CHECK (max_instance_count > 0), -- 20% of cluster capacity
    allocation_percentage DECIMAL(5,2) NOT NULL CHECK (allocation_percentage >= 0 AND allocation_percentage <= 100),

    -- Risk assessment
    risk_score DECIMAL(5,4) NOT NULL CHECK (risk_score >= 0 AND risk_score <= 1),
    meets_safety_threshold BOOLEAN NOT NULL DEFAULT false, -- risk_score >= 0.75

    -- Constraint violation tracking
    exceeds_max_allocation BOOLEAN NOT NULL DEFAULT false, -- allocation_percentage > 20%
    last_violation_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Unique constraint: One allocation record per pool per cluster
    UNIQUE(cluster_id, pool_key)
);

-- Indexes for safety constraint checks
CREATE INDEX idx_pool_alloc_cluster ON pool_allocations(cluster_id);
CREATE INDEX idx_pool_alloc_percentage ON pool_allocations(cluster_id, allocation_percentage DESC);
CREATE INDEX idx_pool_alloc_violations ON pool_allocations(exceeds_max_allocation, last_violation_at);
CREATE INDEX idx_pool_alloc_risk ON pool_allocations(risk_score);

-- Trigger to auto-update updated_at timestamp
CREATE TRIGGER trigger_update_pool_allocations_timestamp
    BEFORE UPDATE ON pool_allocations
    FOR EACH ROW
    EXECUTE FUNCTION update_interruption_feedback_timestamp();

COMMENT ON TABLE pool_allocations IS 'Tracks Spot pool allocations to enforce 20% max per pool safety constraint';
COMMENT ON COLUMN pool_allocations.pool_key IS 'Unique pool identifier: instance_type:availability_zone (e.g., m5.large:us-east-1a)';
COMMENT ON COLUMN pool_allocations.allocation_percentage IS 'Percentage of cluster capacity in this pool (must be <= 20%)';
COMMENT ON COLUMN pool_allocations.exceeds_max_allocation IS 'Safety flag: TRUE if allocation > 20%';

-- ==============================================================================
-- TABLE 3: az_distribution
-- ==============================================================================
-- Purpose: Track availability zone distribution to enforce 3+ AZ minimum constraint
-- Key Feature: Ensures geographic diversity (multi-AZ resilience)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS az_distribution (
    -- Primary identification
    distribution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES clusters(cluster_id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,

    -- AZ identification
    availability_zone VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,

    -- Instance counts
    total_instances INTEGER NOT NULL DEFAULT 0 CHECK (total_instances >= 0),
    spot_instances INTEGER NOT NULL DEFAULT 0 CHECK (spot_instances >= 0),
    on_demand_instances INTEGER NOT NULL DEFAULT 0 CHECK (on_demand_instances >= 0),

    -- Distribution metrics
    percentage_of_cluster DECIMAL(5,2) NOT NULL CHECK (percentage_of_cluster >= 0 AND percentage_of_cluster <= 100),
    percentage_of_spot DECIMAL(5,2) NOT NULL CHECK (percentage_of_spot >= 0 AND percentage_of_spot <= 100),

    -- Safety compliance
    meets_minimum_distribution BOOLEAN NOT NULL DEFAULT false, -- At least 10% of cluster
    is_primary_az BOOLEAN NOT NULL DEFAULT false, -- Largest allocation

    -- Metadata
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Unique constraint: One record per AZ per cluster
    UNIQUE(cluster_id, availability_zone)
);

-- Indexes for AZ distribution queries
CREATE INDEX idx_az_dist_cluster ON az_distribution(cluster_id);
CREATE INDEX idx_az_dist_percentage ON az_distribution(cluster_id, percentage_of_cluster DESC);
CREATE INDEX idx_az_dist_safety ON az_distribution(meets_minimum_distribution);

COMMENT ON TABLE az_distribution IS 'Tracks AZ distribution to enforce 3+ AZ minimum safety constraint';
COMMENT ON COLUMN az_distribution.meets_minimum_distribution IS 'Safety flag: TRUE if AZ has >= 10% of cluster capacity';
COMMENT ON COLUMN az_distribution.is_primary_az IS 'Flag for AZ with largest allocation (for monitoring)';

-- ==============================================================================
-- TABLE 4: safety_violations
-- ==============================================================================
-- Purpose: Audit log of ALL safety constraint violations (risk, pool, AZ, buffer)
-- Key Feature: Transparency and compliance tracking
-- ==============================================================================

CREATE TABLE IF NOT EXISTS safety_violations (
    -- Primary identification
    violation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES clusters(cluster_id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,

    -- Violation classification
    violation_type VARCHAR(100) NOT NULL CHECK (violation_type IN (
        'risk_threshold',        -- risk_score < 0.75
        'pool_concentration',    -- single pool > 20%
        'az_distribution',       -- fewer than 3 AZs
        'on_demand_buffer',      -- On-Demand buffer < 15%
        'multiple_violations'    -- Combination of above
    )),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),

    -- Violation details
    description TEXT NOT NULL,
    recommendation_data JSONB, -- Store the rejected recommendation for audit
    safe_alternative_data JSONB, -- Store the safe alternative created

    -- Resolution tracking
    action_taken TEXT NOT NULL,
    was_rejected BOOLEAN NOT NULL DEFAULT false, -- Was recommendation rejected?
    was_modified BOOLEAN NOT NULL DEFAULT false, -- Was recommendation modified to safe alternative?

    -- Timing
    detected_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP,
    resolution_duration_seconds INTEGER,

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for violation queries and reporting
CREATE INDEX idx_violations_cluster ON safety_violations(cluster_id, detected_at DESC);
CREATE INDEX idx_violations_type ON safety_violations(violation_type, severity);
CREATE INDEX idx_violations_unresolved ON safety_violations(resolved_at) WHERE resolved_at IS NULL;
CREATE INDEX idx_violations_customer ON safety_violations(customer_id, detected_at DESC);

COMMENT ON TABLE safety_violations IS 'Audit log of all safety constraint violations - enables compliance tracking';
COMMENT ON COLUMN safety_violations.violation_type IS 'Type: risk_threshold, pool_concentration, az_distribution, on_demand_buffer';
COMMENT ON COLUMN safety_violations.action_taken IS 'What SafetyEnforcer did: rejected, created_alternative, modified_pools';

-- ==============================================================================
-- TABLE 5: risk_score_adjustments (FOR ML SERVER DATABASE)
-- ==============================================================================
-- Purpose: Track ML learning adjustments to risk scores (customer feedback loop)
-- Key Feature: Enables adaptive risk scoring (0% → 25% customer weight)
-- Location: This table goes in ML Server database, not Core Platform
-- ==============================================================================
-- NOTE: This SQL will be added to ml-server/database/migrations/
-- Including here for completeness of the migration plan
-- ==============================================================================

-- This table is created in Phase 1C (ML Server database migration)
-- See: ml-server/database/migrations/002_add_risk_score_adjustments.sql

-- ==============================================================================
-- HELPER VIEWS
-- ==============================================================================

-- View: Active Safety Violations (unresolved)
CREATE OR REPLACE VIEW active_safety_violations AS
SELECT
    violation_id,
    cluster_id,
    customer_id,
    violation_type,
    severity,
    description,
    detected_at,
    EXTRACT(EPOCH FROM (NOW() - detected_at)) / 3600 AS hours_unresolved
FROM safety_violations
WHERE resolved_at IS NULL
ORDER BY severity DESC, detected_at DESC;

COMMENT ON VIEW active_safety_violations IS 'Currently unresolved safety violations requiring attention';

-- View: Cluster Safety Summary
CREATE OR REPLACE VIEW cluster_safety_summary AS
SELECT
    c.cluster_id,
    c.cluster_name,
    c.customer_id,

    -- Pool allocation safety
    COUNT(DISTINCT pa.pool_key) AS total_pools,
    COUNT(DISTINCT pa.pool_key) FILTER (WHERE pa.exceeds_max_allocation = true) AS pools_exceeding_20pct,
    MAX(pa.allocation_percentage) AS max_pool_allocation_pct,

    -- AZ distribution safety
    COUNT(DISTINCT azd.availability_zone) AS total_azs,
    COUNT(DISTINCT azd.availability_zone) FILTER (WHERE azd.meets_minimum_distribution = true) AS azs_meeting_minimum,

    -- Violation history
    COUNT(DISTINCT sv.violation_id) AS total_violations_last_30_days,
    COUNT(DISTINCT sv.violation_id) FILTER (WHERE sv.resolved_at IS NULL) AS active_violations,

    -- Overall safety score (0.0 - 1.0)
    CASE
        WHEN COUNT(DISTINCT azd.availability_zone) >= 3
         AND MAX(pa.allocation_percentage) <= 20.0
         AND COUNT(DISTINCT sv.violation_id) FILTER (WHERE sv.resolved_at IS NULL) = 0
        THEN 1.0
        ELSE 0.5
    END AS safety_score

FROM clusters c
LEFT JOIN pool_allocations pa ON c.cluster_id = pa.cluster_id
LEFT JOIN az_distribution azd ON c.cluster_id = azd.cluster_id
LEFT JOIN safety_violations sv ON c.cluster_id = sv.cluster_id
    AND sv.detected_at >= NOW() - INTERVAL '30 days'
GROUP BY c.cluster_id, c.cluster_name, c.customer_id;

COMMENT ON VIEW cluster_safety_summary IS 'High-level safety metrics per cluster for monitoring dashboard';

-- ==============================================================================
-- GRANT PERMISSIONS
-- ==============================================================================

-- Grant read/write to application user
GRANT SELECT, INSERT, UPDATE, DELETE ON interruption_feedback TO core_platform;
GRANT SELECT, INSERT, UPDATE, DELETE ON pool_allocations TO core_platform;
GRANT SELECT, INSERT, UPDATE, DELETE ON az_distribution TO core_platform;
GRANT SELECT, INSERT, UPDATE, DELETE ON safety_violations TO core_platform;

-- Grant read-only to reporting/analytics user
GRANT SELECT ON interruption_feedback TO core_platform_readonly;
GRANT SELECT ON pool_allocations TO core_platform_readonly;
GRANT SELECT ON az_distribution TO core_platform_readonly;
GRANT SELECT ON safety_violations TO core_platform_readonly;
GRANT SELECT ON active_safety_violations TO core_platform_readonly;
GRANT SELECT ON cluster_safety_summary TO core_platform_readonly;

-- ==============================================================================
-- VALIDATION QUERIES (For testing after migration)
-- ==============================================================================

-- Test 1: Verify all tables created
DO $$
DECLARE
    missing_tables TEXT[];
BEGIN
    SELECT ARRAY_AGG(table_name) INTO missing_tables
    FROM (VALUES
        ('interruption_feedback'),
        ('pool_allocations'),
        ('az_distribution'),
        ('safety_violations')
    ) AS expected(table_name)
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = expected.table_name
        AND table_schema = 'public'
    );

    IF missing_tables IS NOT NULL THEN
        RAISE EXCEPTION 'Migration failed - missing tables: %', missing_tables;
    ELSE
        RAISE NOTICE 'SUCCESS: All 4 tables created successfully';
    END IF;
END $$;

-- Test 2: Verify indexes created
DO $$
DECLARE
    index_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename IN (
        'interruption_feedback',
        'pool_allocations',
        'az_distribution',
        'safety_violations'
    );

    IF index_count < 15 THEN
        RAISE WARNING 'Expected 15+ indexes, found %', index_count;
    ELSE
        RAISE NOTICE 'SUCCESS: % indexes created', index_count;
    END IF;
END $$;

-- Test 3: Verify views created
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'active_safety_violations') THEN
        RAISE EXCEPTION 'View active_safety_violations not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'cluster_safety_summary') THEN
        RAISE EXCEPTION 'View cluster_safety_summary not created';
    END IF;

    RAISE NOTICE 'SUCCESS: All views created';
END $$;

-- ==============================================================================
-- MIGRATION COMPLETE
-- ==============================================================================

-- Log migration completion
INSERT INTO schema_migrations (version, description, applied_at)
VALUES (
    '002',
    'Add customer feedback loop and safety constraint enforcement tables',
    NOW()
) ON CONFLICT (version) DO NOTHING;

-- Display summary
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '=====================================================================';
    RAISE NOTICE 'Migration 002 - Customer Feedback + Safety Constraints';
    RAISE NOTICE '=====================================================================';
    RAISE NOTICE 'Tables created:';
    RAISE NOTICE '  ✓ interruption_feedback (ML learning from real interruptions)';
    RAISE NOTICE '  ✓ pool_allocations (20%% max per pool enforcement)';
    RAISE NOTICE '  ✓ az_distribution (3+ AZ minimum enforcement)';
    RAISE NOTICE '  ✓ safety_violations (audit log for compliance)';
    RAISE NOTICE '';
    RAISE NOTICE 'Views created:';
    RAISE NOTICE '  ✓ active_safety_violations (unresolved violations)';
    RAISE NOTICE '  ✓ cluster_safety_summary (per-cluster safety metrics)';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Deploy ML Server with feedback API endpoints';
    RAISE NOTICE '  2. Deploy Core Platform with SafetyEnforcer service';
    RAISE NOTICE '  3. Monitor safety_violations table for rejected recommendations';
    RAISE NOTICE '=====================================================================';
END $$;
