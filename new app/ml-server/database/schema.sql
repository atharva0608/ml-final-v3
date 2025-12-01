-- ==============================================================================
-- CloudOptim ML Server - Database Migration 002
-- Add Risk Score Adjustments Table for Customer Feedback Loop
-- ==============================================================================
-- Purpose: Enable adaptive risk scoring with customer feedback (0% → 25% weight)
-- Author: Claude/Architecture Team
-- Date: 2025-12-01
-- Dependencies: 001_initial_schema.sql (base ML Server tables)
-- ==============================================================================

-- ==============================================================================
-- TABLE: risk_score_adjustments
-- ==============================================================================
-- Purpose: Track ML learning adjustments to risk scores based on real interruptions
-- Key Feature: Enables customer feedback loop that grows from 0% → 25% weight over 12 months
-- Data Source: Populated from Core Platform interruption_feedback table
-- ==============================================================================

CREATE TABLE IF NOT EXISTS risk_score_adjustments (
    -- Primary identification
    adjustment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pool identification (granular: instance_type + AZ + region)
    instance_type VARCHAR(50) NOT NULL,
    availability_zone VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,

    -- Risk score components
    base_score DECIMAL(5,4) NOT NULL CHECK (base_score >= 0 AND base_score <= 1), -- From AWS Spot Advisor
    customer_adjustment DECIMAL(6,5) NOT NULL DEFAULT 0.0 CHECK (customer_adjustment >= -1 AND customer_adjustment <= 1), -- Learning delta
    final_score DECIMAL(5,4) NOT NULL CHECK (final_score >= 0 AND final_score <= 1), -- Combined score

    -- Confidence tracking
    confidence DECIMAL(5,4) NOT NULL DEFAULT 0.0 CHECK (confidence >= 0 AND confidence <= 1), -- 0.0 = no data, 1.0 = high confidence
    data_points_count INTEGER NOT NULL DEFAULT 0 CHECK (data_points_count >= 0), -- How many interruptions observed

    -- Temporal pattern learning
    temporal_patterns JSONB, -- {day_of_week: {0: 0.85, 1: 0.90, ...}, hour_of_day: {0: 0.95, 8: 0.80, ...}}
    has_temporal_patterns BOOLEAN NOT NULL DEFAULT false,

    -- Workload-specific learning
    workload_patterns JSONB, -- {web: 0.88, database: 0.92, ml: 0.85, batch: 0.90}
    has_workload_patterns BOOLEAN NOT NULL DEFAULT false,

    -- Seasonal pattern detection (for mature datasets)
    seasonal_patterns JSONB, -- {black_friday: 0.70, end_of_quarter: 0.75, holidays: 0.85}
    has_seasonal_patterns BOOLEAN NOT NULL DEFAULT false,

    -- Learning metadata
    first_observation_at TIMESTAMP, -- When we first saw this pool
    last_observation_at TIMESTAMP, -- Most recent interruption data
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
    observation_count INTEGER NOT NULL DEFAULT 0, -- Total observations (including non-interruptions)
    interruption_count INTEGER NOT NULL DEFAULT 0, -- Actual interruptions observed

    -- Derived metrics
    actual_interruption_rate DECIMAL(6,5), -- interruption_count / observation_count
    predicted_interruption_rate DECIMAL(6,5), -- What our model predicted
    prediction_accuracy DECIMAL(5,4), -- How accurate our predictions are

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Unique constraint: One adjustment record per pool
    UNIQUE(instance_type, availability_zone, region)
);

-- Indexes for high-performance queries
CREATE INDEX idx_risk_adj_pool ON risk_score_adjustments(instance_type, region, availability_zone);
CREATE INDEX idx_risk_adj_confidence ON risk_score_adjustments(confidence DESC, data_points_count DESC);
CREATE INDEX idx_risk_adj_final_score ON risk_score_adjustments(final_score);
CREATE INDEX idx_risk_adj_updated ON risk_score_adjustments(last_updated DESC);
CREATE INDEX idx_risk_adj_patterns ON risk_score_adjustments(has_temporal_patterns, has_workload_patterns);

COMMENT ON TABLE risk_score_adjustments IS 'ML learning adjustments to risk scores based on real customer interruptions (enables 0% → 25% feedback weight)';
COMMENT ON COLUMN risk_score_adjustments.base_score IS 'AWS Spot Advisor risk score (static data)';
COMMENT ON COLUMN risk_score_adjustments.customer_adjustment IS 'Learning delta from observed interruptions (-1.0 to +1.0)';
COMMENT ON COLUMN risk_score_adjustments.final_score IS 'Combined risk score used for deployment decisions';
COMMENT ON COLUMN risk_score_adjustments.confidence IS 'Confidence level: 0.0 = no data, 1.0 = high confidence (500+ observations)';
COMMENT ON COLUMN risk_score_adjustments.temporal_patterns IS 'JSON: day_of_week and hour_of_day interruption patterns';
COMMENT ON COLUMN risk_score_adjustments.workload_patterns IS 'JSON: workload-specific interruption patterns (web, database, ml, batch)';
COMMENT ON COLUMN risk_score_adjustments.seasonal_patterns IS 'JSON: seasonal patterns (Black Friday, end-of-quarter, holidays)';

-- ==============================================================================
-- TABLE: feedback_learning_stats
-- ==============================================================================
-- Purpose: Track global learning statistics across all customers
-- Key Feature: Monitors customer feedback weight growth (0% → 25%)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS feedback_learning_stats (
    -- Primary identification
    stat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Time period
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,

    -- Global metrics
    total_interruptions INTEGER NOT NULL DEFAULT 0,
    total_instance_hours INTEGER NOT NULL DEFAULT 0, -- Total Spot instance-hours observed
    total_unique_pools INTEGER NOT NULL DEFAULT 0, -- Unique instance_type:az:region combinations

    -- Learning progress
    pools_with_data INTEGER NOT NULL DEFAULT 0, -- Pools with at least 1 observation
    pools_with_confidence INTEGER NOT NULL DEFAULT 0, -- Pools with confidence >= 0.5
    pools_with_temporal_patterns INTEGER NOT NULL DEFAULT 0,
    pools_with_workload_patterns INTEGER NOT NULL DEFAULT 0,

    -- Customer feedback weight (0% → 25%)
    current_feedback_weight DECIMAL(5,4) NOT NULL CHECK (current_feedback_weight >= 0 AND current_feedback_weight <= 0.25),
    target_feedback_weight DECIMAL(5,4) NOT NULL DEFAULT 0.25, -- Target: 25%

    -- Prediction accuracy
    overall_prediction_accuracy DECIMAL(5,4), -- Across all predictions
    high_confidence_accuracy DECIMAL(5,4), -- For confidence >= 0.8

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Unique constraint: One record per time period
    UNIQUE(period_start, period_end)
);

CREATE INDEX idx_learning_stats_period ON feedback_learning_stats(period_start DESC);
CREATE INDEX idx_learning_stats_weight ON feedback_learning_stats(current_feedback_weight);

COMMENT ON TABLE feedback_learning_stats IS 'Global statistics tracking ML learning progress and customer feedback weight growth';
COMMENT ON COLUMN feedback_learning_stats.current_feedback_weight IS 'Current customer feedback weight in risk formula (0% → 25% over 12 months)';
COMMENT ON COLUMN feedback_learning_stats.total_instance_hours IS 'Cumulative Spot instance-hours observed (moat depth indicator)';

-- ==============================================================================
-- HELPER FUNCTIONS
-- ==============================================================================

-- Function: Calculate customer feedback weight based on data maturity
CREATE OR REPLACE FUNCTION calculate_feedback_weight(
    p_total_instance_hours INTEGER,
    p_total_interruptions INTEGER
) RETURNS DECIMAL(5,4) AS $$
DECLARE
    v_weight DECIMAL(5,4);
BEGIN
    -- Month 1 (0-10K instance-hours): 0% weight
    IF p_total_instance_hours < 10000 THEN
        v_weight := 0.0;

    -- Month 3 (10K-50K instance-hours): 0% → 10% weight
    ELSIF p_total_instance_hours < 50000 THEN
        v_weight := LEAST(0.10, (p_total_instance_hours::DECIMAL / 50000) * 0.10);

    -- Month 6 (50K-200K instance-hours): 10% → 15% weight
    ELSIF p_total_instance_hours < 200000 THEN
        v_weight := 0.10 + LEAST(0.05, ((p_total_instance_hours - 50000)::DECIMAL / 150000) * 0.05);

    -- Month 12 (200K-500K instance-hours): 15% → 25% weight
    ELSIF p_total_instance_hours < 500000 THEN
        v_weight := 0.15 + LEAST(0.10, ((p_total_instance_hours - 200000)::DECIMAL / 300000) * 0.10);

    -- Mature (500K+ instance-hours): 25% weight (full moat)
    ELSE
        v_weight := 0.25;
    END IF;

    RETURN v_weight;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION calculate_feedback_weight IS 'Calculate customer feedback weight based on data maturity (0% → 25% over time)';

-- Function: Update risk score adjustment from new interruption data
CREATE OR REPLACE FUNCTION update_risk_adjustment(
    p_instance_type VARCHAR(50),
    p_availability_zone VARCHAR(50),
    p_region VARCHAR(50),
    p_was_interruption BOOLEAN,
    p_base_score DECIMAL(5,4),
    p_temporal_data JSONB DEFAULT NULL,
    p_workload_type VARCHAR(100) DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_existing_record RECORD;
    v_new_adjustment DECIMAL(6,5);
    v_new_confidence DECIMAL(5,4);
    v_new_final_score DECIMAL(5,4);
BEGIN
    -- Get existing record
    SELECT * INTO v_existing_record
    FROM risk_score_adjustments
    WHERE instance_type = p_instance_type
      AND availability_zone = p_availability_zone
      AND region = p_region;

    -- Calculate new metrics
    IF v_existing_record IS NOT NULL THEN
        -- Update existing record
        IF p_was_interruption THEN
            -- Interruption occurred - adjust risk downward
            v_new_adjustment := v_existing_record.customer_adjustment - 0.01;
        ELSE
            -- No interruption - adjust risk upward slightly
            v_new_adjustment := v_existing_record.customer_adjustment + 0.005;
        END IF;

        -- Clamp adjustment to [-0.3, +0.3] range
        v_new_adjustment := GREATEST(-0.3, LEAST(0.3, v_new_adjustment));

        -- Calculate confidence (0.0 → 1.0 based on data points)
        v_new_confidence := LEAST(1.0, (v_existing_record.data_points_count + 1)::DECIMAL / 500);

        -- Calculate final score
        v_new_final_score := GREATEST(0.0, LEAST(1.0, p_base_score + v_new_adjustment));

        -- Update record
        UPDATE risk_score_adjustments
        SET
            base_score = p_base_score,
            customer_adjustment = v_new_adjustment,
            final_score = v_new_final_score,
            confidence = v_new_confidence,
            data_points_count = data_points_count + 1,
            interruption_count = interruption_count + CASE WHEN p_was_interruption THEN 1 ELSE 0 END,
            observation_count = observation_count + 1,
            last_observation_at = NOW(),
            last_updated = NOW(),
            temporal_patterns = COALESCE(p_temporal_data, temporal_patterns),
            has_temporal_patterns = (p_temporal_data IS NOT NULL OR has_temporal_patterns),
            workload_patterns = CASE
                WHEN p_workload_type IS NOT NULL THEN
                    jsonb_set(
                        COALESCE(workload_patterns, '{}'::jsonb),
                        ARRAY[p_workload_type],
                        to_jsonb(v_new_final_score)
                    )
                ELSE workload_patterns
            END,
            has_workload_patterns = (p_workload_type IS NOT NULL OR has_workload_patterns)
        WHERE instance_type = p_instance_type
          AND availability_zone = p_availability_zone
          AND region = p_region;
    ELSE
        -- Insert new record
        v_new_adjustment := 0.0;
        v_new_confidence := 0.01; -- Start with low confidence
        v_new_final_score := p_base_score;

        INSERT INTO risk_score_adjustments (
            instance_type,
            availability_zone,
            region,
            base_score,
            customer_adjustment,
            final_score,
            confidence,
            data_points_count,
            interruption_count,
            observation_count,
            first_observation_at,
            last_observation_at,
            temporal_patterns,
            has_temporal_patterns,
            workload_patterns,
            has_workload_patterns
        ) VALUES (
            p_instance_type,
            p_availability_zone,
            p_region,
            p_base_score,
            v_new_adjustment,
            v_new_final_score,
            v_new_confidence,
            1, -- data_points_count
            CASE WHEN p_was_interruption THEN 1 ELSE 0 END, -- interruption_count
            1, -- observation_count
            NOW(), -- first_observation_at
            NOW(), -- last_observation_at
            p_temporal_data,
            (p_temporal_data IS NOT NULL),
            CASE WHEN p_workload_type IS NOT NULL THEN jsonb_build_object(p_workload_type, p_base_score) ELSE NULL END,
            (p_workload_type IS NOT NULL)
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_risk_adjustment IS 'Update risk score adjustment from new interruption/observation data';

-- ==============================================================================
-- HELPER VIEWS
-- ==============================================================================

-- View: High Confidence Risk Scores (for production use)
CREATE OR REPLACE VIEW high_confidence_risk_scores AS
SELECT
    instance_type,
    availability_zone,
    region,
    final_score AS risk_score,
    confidence,
    data_points_count,
    interruption_count,
    observation_count,
    actual_interruption_rate,
    has_temporal_patterns,
    has_workload_patterns,
    last_updated
FROM risk_score_adjustments
WHERE confidence >= 0.5 -- Only use scores with moderate+ confidence
ORDER BY confidence DESC, data_points_count DESC;

COMMENT ON VIEW high_confidence_risk_scores IS 'Risk scores with confidence >= 0.5 (safe for production use)';

-- View: Learning Progress Summary
CREATE OR REPLACE VIEW learning_progress_summary AS
SELECT
    COUNT(*) AS total_pools,
    COUNT(*) FILTER (WHERE data_points_count > 0) AS pools_with_data,
    COUNT(*) FILTER (WHERE confidence >= 0.3) AS pools_low_confidence,
    COUNT(*) FILTER (WHERE confidence >= 0.5) AS pools_medium_confidence,
    COUNT(*) FILTER (WHERE confidence >= 0.8) AS pools_high_confidence,
    COUNT(*) FILTER (WHERE has_temporal_patterns) AS pools_with_temporal,
    COUNT(*) FILTER (WHERE has_workload_patterns) AS pools_with_workload,
    SUM(data_points_count) AS total_observations,
    SUM(interruption_count) AS total_interruptions,
    AVG(confidence) AS avg_confidence,
    MAX(last_updated) AS most_recent_update
FROM risk_score_adjustments;

COMMENT ON VIEW learning_progress_summary IS 'High-level summary of ML learning progress across all pools';

-- ==============================================================================
-- GRANT PERMISSIONS
-- ==============================================================================

-- Grant read/write to application user
GRANT SELECT, INSERT, UPDATE, DELETE ON risk_score_adjustments TO ml_server;
GRANT SELECT, INSERT, UPDATE, DELETE ON feedback_learning_stats TO ml_server;

-- Grant read-only to reporting user
GRANT SELECT ON risk_score_adjustments TO ml_server_readonly;
GRANT SELECT ON feedback_learning_stats TO ml_server_readonly;
GRANT SELECT ON high_confidence_risk_scores TO ml_server_readonly;
GRANT SELECT ON learning_progress_summary TO ml_server_readonly;

-- Grant execute on functions
GRANT EXECUTE ON FUNCTION calculate_feedback_weight TO ml_server;
GRANT EXECUTE ON FUNCTION update_risk_adjustment TO ml_server;

-- ==============================================================================
-- VALIDATION QUERIES (For testing after migration)
-- ==============================================================================

-- Test 1: Verify tables created
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'risk_score_adjustments') THEN
        RAISE EXCEPTION 'Table risk_score_adjustments not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'feedback_learning_stats') THEN
        RAISE EXCEPTION 'Table feedback_learning_stats not created';
    END IF;

    RAISE NOTICE 'SUCCESS: All tables created';
END $$;

-- Test 2: Test feedback weight function
DO $$
DECLARE
    v_weight DECIMAL(5,4);
BEGIN
    -- Test Month 1 (0% weight)
    v_weight := calculate_feedback_weight(5000, 10);
    IF v_weight != 0.0 THEN
        RAISE EXCEPTION 'Month 1 weight should be 0.0, got %', v_weight;
    END IF;

    -- Test Month 12+ (25% weight)
    v_weight := calculate_feedback_weight(600000, 1200);
    IF v_weight != 0.25 THEN
        RAISE EXCEPTION 'Month 12+ weight should be 0.25, got %', v_weight;
    END IF;

    RAISE NOTICE 'SUCCESS: Feedback weight function working correctly';
END $$;

-- Test 3: Test risk adjustment update function
DO $$
BEGIN
    -- Insert test adjustment
    PERFORM update_risk_adjustment(
        'test.instance',
        'test-az-1a',
        'test-region',
        true, -- was_interruption
        0.85, -- base_score
        NULL,
        'test'
    );

    IF NOT EXISTS (SELECT 1 FROM risk_score_adjustments WHERE instance_type = 'test.instance') THEN
        RAISE EXCEPTION 'Risk adjustment not created';
    END IF;

    -- Clean up test data
    DELETE FROM risk_score_adjustments WHERE instance_type = 'test.instance';

    RAISE NOTICE 'SUCCESS: Risk adjustment update function working';
END $$;

-- ==============================================================================
-- MIGRATION COMPLETE
-- ==============================================================================

-- Log migration completion
INSERT INTO schema_migrations (version, description, applied_at)
VALUES (
    '002',
    'Add risk score adjustments and feedback learning tables',
    NOW()
) ON CONFLICT (version) DO NOTHING;

-- Display summary
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '=====================================================================';
    RAISE NOTICE 'Migration 002 - Risk Score Adjustments (Customer Feedback Loop)';
    RAISE NOTICE '=====================================================================';
    RAISE NOTICE 'Tables created:';
    RAISE NOTICE '  ✓ risk_score_adjustments (adaptive risk scoring)';
    RAISE NOTICE '  ✓ feedback_learning_stats (global learning metrics)';
    RAISE NOTICE '';
    RAISE NOTICE 'Functions created:';
    RAISE NOTICE '  ✓ calculate_feedback_weight (0%% → 25%% weight growth)';
    RAISE NOTICE '  ✓ update_risk_adjustment (ML learning from interruptions)';
    RAISE NOTICE '';
    RAISE NOTICE 'Views created:';
    RAISE NOTICE '  ✓ high_confidence_risk_scores (production-ready scores)';
    RAISE NOTICE '  ✓ learning_progress_summary (learning metrics dashboard)';
    RAISE NOTICE '';
    RAISE NOTICE 'Customer Feedback Weight Growth:';
    RAISE NOTICE '  • Month 1: 0%% (no customer data yet)';
    RAISE NOTICE '  • Month 3: 10%% (10K+ instance-hours observed)';
    RAISE NOTICE '  • Month 6: 15%% (50K+ instance-hours, patterns emerging)';
    RAISE NOTICE '  • Month 12: 25%% (500K+ instance-hours, competitive moat)';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Deploy ML Server feedback API endpoints';
    RAISE NOTICE '  2. Connect Core Platform interruption_feedback → ML Server';
    RAISE NOTICE '  3. Monitor learning_progress_summary view';
    RAISE NOTICE '=====================================================================';
END $$;
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
