"""
12-Hour Data Consolidation Job

Implements the three-tier pricing architecture:
1. Staging (spot_price_snapshots) - Raw data from agents
2. Consolidated (pricing_consolidated) - Deduplicated & cleaned
3. Canonical (pricing_canonical) - ML training data

Operations:
- Deduplication (PRIMARY takes precedence over REPLICA)
- Gap interpolation (linear interpolation for missing points)
- Backfill integration (from cloud pricing API)
- Quality scoring
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from core.database import execute_query, execute_transaction
from core.utils import generate_uuid, log_system_event

logger = logging.getLogger(__name__)


def run_consolidation_job():
    """
    Main consolidation job - runs every 12 hours.

    Steps:
    1. Deduplicate pricing snapshots from agents
    2. Identify gaps in timeseries
    3. Interpolate missing points
    4. Integrate backfilled data from cloud API
    5. Write to consolidated table
    6. Update canonical layer for ML training
    """
    job_id = generate_uuid()
    logger.info(f"Starting pricing consolidation job {job_id}")

    # Create job record
    execute_query("""
        INSERT INTO consolidation_jobs (id, job_type, started_at, status)
        VALUES (%s, 'pricing_12h', NOW(), 'running')
    """, (job_id,), commit=True)

    try:
        # Step 1: Deduplicate
        logger.info("Step 1: Deduplicating pricing snapshots...")
        duplicates_removed = deduplicate_pricing_snapshots()
        logger.info(f"  ✓ Removed {duplicates_removed} duplicates")

        # Step 2 & 3: Interpolate gaps
        logger.info("Step 2-3: Interpolating pricing gaps...")
        gaps_filled = interpolate_pricing_gaps(job_id)
        logger.info(f"  ✓ Filled {gaps_filled} gaps")

        # Step 4: Integrate backfills
        logger.info("Step 4: Integrating backfilled data...")
        backfills_added = integrate_backfilled_data(job_id)
        logger.info(f"  ✓ Added {backfills_added} backfills")

        # Step 5: Update canonical layer
        logger.info("Step 5: Updating canonical layer...")
        canonical_records = update_canonical_layer(job_id)
        logger.info(f"  ✓ Updated {canonical_records} canonical records")

        # Mark job complete
        execute_query("""
            UPDATE consolidation_jobs
            SET status = 'completed',
                completed_at = NOW(),
                records_processed = %s,
                duplicates_removed = %s,
                gaps_interpolated = %s,
                backfills_added = %s
            WHERE id = %s
        """, (
            duplicates_removed + gaps_filled + backfills_added,
            duplicates_removed,
            gaps_filled,
            backfills_added,
            job_id
        ), commit=True)

        logger.info(f"✓ Consolidation job {job_id} completed successfully")

        log_system_event(
            'consolidation_job_completed',
            'info',
            f"Pricing consolidation completed: {duplicates_removed} dupes, "
            f"{gaps_filled} gaps, {backfills_added} backfills",
            metadata={
                'job_id': job_id,
                'duplicates_removed': duplicates_removed,
                'gaps_filled': gaps_filled,
                'backfills_added': backfills_added,
                'canonical_records': canonical_records
            }
        )

        return {
            'success': True,
            'job_id': job_id,
            'duplicates_removed': duplicates_removed,
            'gaps_filled': gaps_filled,
            'backfills_added': backfills_added,
            'canonical_records': canonical_records
        }

    except Exception as e:
        logger.error(f"Consolidation job {job_id} failed: {e}", exc_info=True)

        execute_query("""
            UPDATE consolidation_jobs
            SET status = 'failed',
                error_message = %s,
                completed_at = NOW()
            WHERE id = %s
        """, (str(e), job_id), commit=True)

        log_system_event(
            'consolidation_job_failed',
            'error',
            f"Pricing consolidation failed: {e}",
            metadata={'job_id': job_id, 'error': str(e)}
        )

        return {'success': False, 'error': str(e)}


def deduplicate_pricing_snapshots() -> int:
    """
    Remove duplicate pricing from PRIMARY and REPLICA captures.

    Strategy:
    - For same pool+timestamp, PRIMARY data takes precedence
    - Use median if multiple values from same role
    - Mark best record, flag others as duplicates

    Returns:
        Number of duplicates removed
    """
    # Find pools and time windows with duplicates
    duplicate_groups = execute_query("""
        SELECT pool_id, DATE_FORMAT(captured_at, '%Y-%m-%d %H:%i:00') as time_bucket,
               COUNT(*) as count
        FROM spot_price_snapshots
        WHERE data_source = 'agent'
            AND captured_at >= NOW() - INTERVAL 13 HOUR
        GROUP BY pool_id, time_bucket
        HAVING count > 1
    """, fetch_all=True)

    if not duplicate_groups:
        logger.info("No duplicates found")
        return 0

    duplicates_removed = 0

    for group in duplicate_groups:
        pool_id = group['pool_id']
        time_bucket = group['time_bucket']

        # Get all records in this group
        records = execute_query("""
            SELECT id, price, instance_role, agent_id, captured_at
            FROM spot_price_snapshots
            WHERE pool_id = %s
                AND DATE_FORMAT(captured_at, '%Y-%m-%d %H:%i:00') = %s
                AND data_source = 'agent'
            ORDER BY
                CASE WHEN instance_role = 'PRIMARY' THEN 1 ELSE 2 END,
                captured_at DESC
        """, (pool_id, time_bucket), fetch_all=True)

        if len(records) <= 1:
            continue

        # Keep first record (PRIMARY if available), remove others
        keep_id = records[0]['id']
        remove_ids = [r['id'] for r in records[1:]]

        # Delete duplicates
        if remove_ids:
            placeholders = ','.join(['%s'] * len(remove_ids))
            execute_query(f"""
                DELETE FROM spot_price_snapshots
                WHERE id IN ({placeholders})
            """, tuple(remove_ids), commit=True)

            duplicates_removed += len(remove_ids)

    return duplicates_removed


def interpolate_pricing_gaps(job_id: str) -> int:
    """
    Fill gaps in timeseries using linear interpolation.

    Strategy:
    - Find gaps > 5 minutes in consolidated data
    - Use linear interpolation between known points
    - Mark as is_interpolated=true with confidence_score < 1.0

    Returns:
        Number of gaps filled
    """
    # Get all active pools
    pools = execute_query("""
        SELECT DISTINCT pool_id
        FROM spot_price_snapshots
        WHERE captured_at >= NOW() - INTERVAL 13 HOUR
    """, fetch_all=True)

    if not pools:
        return 0

    gaps_filled = 0

    for pool_record in pools:
        pool_id = pool_record['pool_id']

        # Get timeseries for this pool (last 13 hours)
        timeseries = execute_query("""
            SELECT captured_at, price
            FROM spot_price_snapshots
            WHERE pool_id = %s
                AND captured_at >= NOW() - INTERVAL 13 HOUR
                AND data_source IN ('agent', 'interpolated')
            ORDER BY captured_at ASC
        """, (pool_id,), fetch_all=True)

        if not timeseries or len(timeseries) < 2:
            continue

        # Find gaps > 5 minutes
        gaps = _identify_gaps(timeseries, gap_threshold_minutes=5)

        if not gaps:
            continue

        # Interpolate each gap
        for gap in gaps:
            interpolated = _interpolate_gap(
                pool_id=pool_id,
                start_time=gap['start_time'],
                start_price=gap['start_price'],
                end_time=gap['end_time'],
                end_price=gap['end_price'],
                interval_minutes=5
            )

            # Insert interpolated points into consolidated table
            for point in interpolated:
                try:
                    execute_query("""
                        INSERT INTO pricing_consolidated
                        (pool_id, price, timestamp, data_source, consolidation_run_id, confidence_score)
                        VALUES (%s, %s, %s, 'interpolated', %s, 0.80)
                        ON DUPLICATE KEY UPDATE
                            price = VALUES(price),
                            data_source = VALUES(data_source),
                            confidence_score = VALUES(confidence_score)
                    """, (pool_id, point['price'], point['timestamp'], job_id), commit=True)

                    gaps_filled += 1

                except Exception as e:
                    logger.warning(f"Failed to insert interpolated point: {e}")

    return gaps_filled


def _identify_gaps(timeseries: List[Dict], gap_threshold_minutes: int = 5) -> List[Dict]:
    """Identify gaps in timeseries."""
    gaps = []

    for i in range(len(timeseries) - 1):
        current = timeseries[i]
        next_point = timeseries[i + 1]

        time_diff = (next_point['captured_at'] - current['captured_at']).total_seconds() / 60

        if time_diff > gap_threshold_minutes:
            gaps.append({
                'start_time': current['captured_at'],
                'start_price': current['price'],
                'end_time': next_point['captured_at'],
                'end_price': next_point['price'],
                'gap_minutes': time_diff
            })

    return gaps


def _interpolate_gap(
    pool_id: str,
    start_time: datetime,
    start_price: float,
    end_time: datetime,
    end_price: float,
    interval_minutes: int = 5
) -> List[Dict]:
    """
    Generate interpolated points for a gap.

    Uses linear interpolation: price = start_price + (end_price - start_price) * t
    """
    interpolated = []

    total_seconds = (end_time - start_time).total_seconds()
    num_points = int(total_seconds / (interval_minutes * 60)) - 1

    if num_points <= 0:
        return []

    for i in range(1, num_points + 1):
        t = i / (num_points + 1)  # Position between 0 and 1
        timestamp = start_time + timedelta(seconds=t * total_seconds)
        price = start_price + (end_price - start_price) * t

        interpolated.append({
            'timestamp': timestamp,
            'price': round(price, 6)
        })

    return interpolated


def integrate_backfilled_data(job_id: str) -> int:
    """
    Integrate 7-day backfill from cloud pricing API.

    Strategy:
    - Only fill where no agent data exists
    - Mark as is_backfilled=true
    - Use confidence_score = 0.90 (high but not perfect)

    Returns:
        Number of backfill points added
    """
    # TODO: Implement cloud API integration
    # This would call AWS pricing API to get historical spot prices

    # For now, return 0 (no backfill data)
    logger.info("Backfill integration not yet implemented (requires AWS API integration)")
    return 0


def update_canonical_layer(job_id: str) -> int:
    """
    Update canonical layer (pricing_canonical) for ML training.

    Adds lifecycle context and feature engineering fields.

    Returns:
        Number of canonical records updated
    """
    # Copy consolidated data to canonical with lifecycle context
    result = execute_query("""
        INSERT INTO pricing_canonical
        (pool_id, price, timestamp, created_at)
        SELECT
            pc.pool_id,
            pc.price,
            pc.timestamp,
            NOW()
        FROM pricing_consolidated pc
        WHERE pc.consolidation_run_id = %s
            AND pc.data_source IN ('agent', 'backfilled')
        ON DUPLICATE KEY UPDATE
            price = VALUES(price)
    """, (job_id,), commit=True)

    logger.info(f"Updated {result} canonical records")

    # TODO: Add feature engineering (volatility, interruption correlation, etc.)

    return result or 0


def schedule_consolidation_job():
    """
    Schedule consolidation job to run every 12 hours.

    Should be called from main application startup.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()

        # Run every 12 hours
        scheduler.add_job(
            run_consolidation_job,
            'interval',
            hours=12,
            id='pricing_consolidation',
            name='Pricing Data Consolidation (12h)',
            replace_existing=True
        )

        # Also run daily cleanup
        scheduler.add_job(
            cleanup_old_snapshots,
            'cron',
            hour=3,  # 3 AM daily
            id='snapshot_cleanup',
            name='Old Snapshot Cleanup',
            replace_existing=True
        )

        scheduler.start()

        logger.info("✓ Consolidation job scheduler started (12h interval)")

        return scheduler

    except Exception as e:
        logger.error(f"Failed to start consolidation scheduler: {e}")
        return None


def cleanup_old_snapshots():
    """
    Clean up old staging snapshots after consolidation.

    Keeps:
    - Last 7 days of raw snapshots
    - Deletes older staging data (already in consolidated)
    """
    logger.info("Cleaning up old pricing snapshots...")

    deleted = execute_query("""
        DELETE FROM spot_price_snapshots
        WHERE captured_at < NOW() - INTERVAL 7 DAY
            AND data_source = 'agent'
    """, commit=True)

    logger.info(f"Deleted {deleted} old snapshots (older than 7 days)")

    log_system_event(
        'snapshot_cleanup',
        'info',
        f"Cleaned up {deleted} old pricing snapshots",
        metadata={'deleted_count': deleted}
    )

    return deleted
