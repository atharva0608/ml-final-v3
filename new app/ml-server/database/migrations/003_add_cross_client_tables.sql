-- Migration: Add Cross-Client Learning Tables
-- Purpose: Support cross-client pattern detection and proactive rebalancing
-- Date: 2025-12-01
-- Author: Architecture Team

-- ============================================================================
-- 1. Add customer_id to interruption_feedback table (if not exists)
-- ============================================================================

ALTER TABLE interruption_feedback
ADD COLUMN IF NOT EXISTS customer_id UUID;

-- Add foreign key constraint (assuming customers table exists in core-platform)
-- If customers table doesn't exist in ML Server database, comment this out
-- ALTER TABLE interruption_feedback
-- ADD CONSTRAINT fk_interruption_customer
-- FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
-- ON DELETE SET NULL;

-- Add index for cross-client queries
CREATE INDEX IF NOT EXISTS idx_interruption_cross_client
ON interruption_feedback(instance_type, availability_zone, region, interruption_time);

-- Add index for customer lookups
CREATE INDEX IF NOT EXISTS idx_interruption_customer
ON interruption_feedback(customer_id, interruption_time);

COMMENT ON COLUMN interruption_feedback.customer_id IS 'Customer ID for cross-client pattern detection';
COMMENT ON INDEX idx_interruption_cross_client IS 'Optimizes cross-client pattern queries within time windows';

-- ============================================================================
-- 2. Create proactive_rebalance_jobs table
-- ============================================================================

CREATE TABLE IF NOT EXISTS proactive_rebalance_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,
    cluster_id UUID,
    source_instance_type VARCHAR(50) NOT NULL,
    source_availability_zone VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,
    reason TEXT NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'HIGH',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    target_instance_type VARCHAR(50),
    target_availability_zone VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for proactive_rebalance_jobs
CREATE INDEX IF NOT EXISTS idx_rebalance_jobs_status
ON proactive_rebalance_jobs(status, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_rebalance_jobs_customer
ON proactive_rebalance_jobs(customer_id, status);

CREATE INDEX IF NOT EXISTS idx_rebalance_jobs_pool
ON proactive_rebalance_jobs(source_instance_type, source_availability_zone, region);

CREATE INDEX IF NOT EXISTS idx_rebalance_jobs_created
ON proactive_rebalance_jobs(created_at DESC);

-- Comments for documentation
COMMENT ON TABLE proactive_rebalance_jobs IS 'Proactive rebalancing jobs created when cross-client patterns detect risky pools';
COMMENT ON COLUMN proactive_rebalance_jobs.job_id IS 'Unique job identifier';
COMMENT ON COLUMN proactive_rebalance_jobs.customer_id IS 'Customer to be proactively rebalanced';
COMMENT ON COLUMN proactive_rebalance_jobs.cluster_id IS 'Cluster ID (optional, for targeted rebalancing)';
COMMENT ON COLUMN proactive_rebalance_jobs.source_instance_type IS 'Risky instance type to move away from';
COMMENT ON COLUMN proactive_rebalance_jobs.source_availability_zone IS 'Risky AZ to move away from';
COMMENT ON COLUMN proactive_rebalance_jobs.reason IS 'Reason for proactive rebalancing (e.g., "Confirmed risky pool (3 clients interrupted)")';
COMMENT ON COLUMN proactive_rebalance_jobs.priority IS 'Job priority: HIGH, MEDIUM, LOW';
COMMENT ON COLUMN proactive_rebalance_jobs.status IS 'Job status: PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED';
COMMENT ON COLUMN proactive_rebalance_jobs.target_instance_type IS 'Target instance type (determined by Core Platform)';
COMMENT ON COLUMN proactive_rebalance_jobs.target_availability_zone IS 'Target AZ (determined by Core Platform)';
COMMENT ON COLUMN proactive_rebalance_jobs.metadata IS 'Additional metadata (pattern analysis, risk scores, etc.)';

-- ============================================================================
-- 3. Create view for cross-client pattern monitoring
-- ============================================================================

CREATE OR REPLACE VIEW cross_client_pattern_summary AS
SELECT
    instance_type,
    availability_zone,
    region,
    DATE_TRUNC('hour', interruption_time) AS hour_bucket,
    COUNT(DISTINCT customer_id) AS affected_clients_count,
    COUNT(*) AS total_interruptions,
    ARRAY_AGG(DISTINCT customer_id) AS affected_customer_ids,
    MIN(interruption_time) AS first_interruption,
    MAX(interruption_time) AS last_interruption,
    CASE
        WHEN COUNT(DISTINCT customer_id) >= 3 THEN 'CONFIRMED_RISKY'
        WHEN COUNT(DISTINCT customer_id) >= 2 THEN 'UNCERTAIN'
        ELSE 'NORMAL'
    END AS risk_level,
    AVG(risk_score_at_deployment)::DECIMAL(5,4) AS avg_risk_score
FROM interruption_feedback
WHERE interruption_time >= NOW() - INTERVAL '24 hours'
GROUP BY instance_type, availability_zone, region, DATE_TRUNC('hour', interruption_time)
HAVING COUNT(DISTINCT customer_id) >= 2  -- Only show patterns (2+ clients)
ORDER BY DATE_TRUNC('hour', interruption_time) DESC, affected_clients_count DESC;

COMMENT ON VIEW cross_client_pattern_summary IS 'Real-time monitoring of cross-client interruption patterns (last 24 hours)';

-- ============================================================================
-- 4. Create function to get pool risk status
-- ============================================================================

CREATE OR REPLACE FUNCTION get_pool_risk_status(
    p_instance_type VARCHAR,
    p_availability_zone VARCHAR,
    p_region VARCHAR,
    p_time_window_minutes INTEGER DEFAULT 60
)
RETURNS TABLE (
    risk_level VARCHAR,
    affected_clients_count BIGINT,
    recent_interruptions BIGINT,
    affected_customer_ids UUID[],
    first_interruption_time TIMESTAMP,
    last_interruption_time TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE
            WHEN COUNT(DISTINCT customer_id) >= 3 THEN 'CONFIRMED_RISKY'::VARCHAR
            WHEN COUNT(DISTINCT customer_id) >= 2 THEN 'UNCERTAIN'::VARCHAR
            ELSE 'NORMAL'::VARCHAR
        END AS risk_level,
        COUNT(DISTINCT customer_id) AS affected_clients_count,
        COUNT(*) AS recent_interruptions,
        ARRAY_AGG(DISTINCT customer_id) AS affected_customer_ids,
        MIN(interruption_time) AS first_interruption_time,
        MAX(interruption_time) AS last_interruption_time
    FROM interruption_feedback
    WHERE instance_type = p_instance_type
      AND availability_zone = p_availability_zone
      AND region = p_region
      AND interruption_time >= NOW() - (p_time_window_minutes || ' minutes')::INTERVAL
      AND interruption_time <= NOW();
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_pool_risk_status IS 'Get current risk status for a pool based on recent interruptions';

-- ============================================================================
-- 5. Create function to get pending rebalance jobs
-- ============================================================================

CREATE OR REPLACE FUNCTION get_pending_rebalance_jobs(
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    job_id UUID,
    customer_id UUID,
    cluster_id UUID,
    source_instance_type VARCHAR,
    source_availability_zone VARCHAR,
    region VARCHAR,
    reason TEXT,
    priority VARCHAR,
    created_at TIMESTAMP,
    age_seconds BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        j.job_id,
        j.customer_id,
        j.cluster_id,
        j.source_instance_type,
        j.source_availability_zone,
        j.region,
        j.reason,
        j.priority,
        j.created_at,
        EXTRACT(EPOCH FROM (NOW() - j.created_at))::BIGINT AS age_seconds
    FROM proactive_rebalance_jobs j
    WHERE j.status = 'PENDING'
    ORDER BY
        CASE j.priority
            WHEN 'HIGH' THEN 1
            WHEN 'MEDIUM' THEN 2
            WHEN 'LOW' THEN 3
            ELSE 4
        END,
        j.created_at ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_pending_rebalance_jobs IS 'Get pending rebalance jobs ordered by priority and age';

-- ============================================================================
-- 6. Insert initial test data (optional - comment out for production)
-- ============================================================================

-- Uncomment for testing:
-- INSERT INTO proactive_rebalance_jobs (
--     customer_id, source_instance_type, source_availability_zone, region, reason, priority, status
-- ) VALUES (
--     gen_random_uuid(), 'm5.large', 'us-east-1a', 'us-east-1',
--     'Test: Confirmed risky pool (3 clients interrupted)', 'HIGH', 'PENDING'
-- );

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Verify tables created
SELECT
    tablename,
    schemaname
FROM pg_tables
WHERE tablename IN ('proactive_rebalance_jobs', 'interruption_feedback')
ORDER BY tablename;

-- Verify indexes created
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE tablename IN ('proactive_rebalance_jobs', 'interruption_feedback')
ORDER BY tablename, indexname;

-- Summary
DO $$
BEGIN
    RAISE NOTICE 'Migration 003: Cross-Client Learning Tables - COMPLETED';
    RAISE NOTICE '✅ Added customer_id to interruption_feedback';
    RAISE NOTICE '✅ Created proactive_rebalance_jobs table';
    RAISE NOTICE '✅ Created cross_client_pattern_summary view';
    RAISE NOTICE '✅ Created get_pool_risk_status() function';
    RAISE NOTICE '✅ Created get_pending_rebalance_jobs() function';
    RAISE NOTICE '✅ Added indexes for cross-client queries';
END $$;
