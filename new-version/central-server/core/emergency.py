"""
Emergency Flow Orchestration for Rebalance and Termination Notices.

Handles AWS spot interruption notices with:
- Rebalance recommendation (best case: 2-minute window)
- Termination notice (worst case: immediate)
- Fastest pool selection for emergency replicas
- Automatic promotion with health verification
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from core.database import execute_query, execute_transaction
from core.utils import log_system_event, create_notification, generate_uuid

logger = logging.getLogger(__name__)


def handle_rebalance_notice(agent_id: str, notice_time: datetime) -> Optional[str]:
    """
    Handle AWS rebalance recommendation (best case: 2-minute window).

    Actions:
    1. Mark agent with rebalance status
    2. Create emergency replica in fastest-boot pool
    3. Monitor for termination notice or completion

    Args:
        agent_id: Agent UUID
        notice_time: Timestamp when rebalance notice received

    Returns:
        replica_id if created, None if failed
    """
    logger.warning(f"Rebalance notice received for agent {agent_id}")

    # Get agent details
    agent = execute_query(
        "SELECT * FROM agents WHERE id = %s",
        (agent_id,),
        fetch_one=True
    )

    if not agent:
        logger.error(f"Agent {agent_id} not found for rebalance notice")
        return None

    # Update agent notice status
    execute_query("""
        UPDATE agents
        SET notice_status = 'rebalance',
            notice_received_at = %s,
            notice_deadline = %s,
            last_rebalance_recommendation_at = NOW(),
            last_emergency_at = NOW()
        WHERE id = %s
    """, (
        notice_time,
        notice_time + timedelta(minutes=2),
        agent_id
    ), commit=True)

    # Create emergency replica
    replica_id = create_emergency_replica(
        agent_id=agent_id,
        reason='rebalance-recommendation',
        deadline_seconds=120
    )

    if replica_id:
        # Log system event
        log_system_event(
            'rebalance_notice',
            'warning',
            f"Rebalance notice for agent {agent['logical_agent_id']}, "
            f"emergency replica {replica_id} created",
            client_id=agent['client_id'],
            agent_id=agent_id,
            metadata={
                'replica_id': replica_id,
                'deadline': '120s',
                'pool_id': agent.get('fastest_boot_pool_id')
            }
        )

        # Create notification for client
        create_notification(
            f"⚠️ Rebalance notice for {agent['hostname']} - Emergency replica created",
            'warning',
            agent['client_id']
        )

    return replica_id


def handle_termination_notice(agent_id: str, termination_time: datetime) -> Optional[str]:
    """
    Handle AWS termination notice (worst case: immediate).

    Actions:
    1. Mark agent with termination status
    2. Create emergency replica if not exists
    3. Initiate immediate promotion if replica ready

    Args:
        agent_id: Agent UUID
        termination_time: Expected termination timestamp

    Returns:
        replica_id if created/found, None if failed
    """
    logger.critical(f"⚠️ TERMINATION NOTICE received for agent {agent_id}")

    # Get agent details
    agent = execute_query(
        "SELECT * FROM agents WHERE id = %s",
        (agent_id,),
        fetch_one=True
    )

    if not agent:
        logger.error(f"Agent {agent_id} not found for termination notice")
        return None

    # Update agent notice status
    execute_query("""
        UPDATE agents
        SET notice_status = 'termination',
            notice_received_at = NOW(),
            notice_deadline = %s,
            last_termination_notice_at = NOW(),
            last_emergency_at = NOW(),
            emergency_replica_count = emergency_replica_count + 1
        WHERE id = %s
    """, (termination_time, agent_id), commit=True)

    # Check for existing ready replica
    replica = execute_query("""
        SELECT id, status, boot_time_seconds
        FROM replica_instances
        WHERE agent_id = %s
            AND status IN ('ready', 'syncing', 'launching')
            AND is_active = TRUE
        ORDER BY created_at DESC
        LIMIT 1
    """, (agent_id,), fetch_one=True)

    if replica:
        replica_id = replica['id']
        logger.info(f"Existing replica {replica_id} found (status: {replica['status']})")

        # If replica is ready, promote immediately
        if replica['status'] == 'ready':
            logger.info(f"Promoting replica {replica_id} immediately")
            success = promote_replica(replica_id, emergency=True)

            if success:
                create_notification(
                    f"🚨 Termination notice - Replica promoted for {agent['hostname']}",
                    'error',
                    agent['client_id']
                )
            else:
                logger.error(f"Failed to promote replica {replica_id}")

    else:
        # No replica exists - create emergency replica
        logger.warning(f"No replica found for {agent_id}, creating emergency replica")

        replica_id = create_emergency_replica(
            agent_id=agent_id,
            reason='termination-notice',
            deadline_seconds=60  # Even faster
        )

        if replica_id:
            create_notification(
                f"🚨 Termination notice for {agent['hostname']} - Emergency replica created",
                'error',
                agent['client_id']
            )

    # Log system event
    log_system_event(
        'termination_notice',
        'critical',
        f"Termination notice for agent {agent['logical_agent_id']}",
        client_id=agent['client_id'],
        agent_id=agent_id,
        metadata={
            'replica_id': replica_id if replica else None,
            'termination_time': termination_time.isoformat() if termination_time else None
        }
    )

    return replica_id


def create_emergency_replica(
    agent_id: str,
    reason: str,
    deadline_seconds: int
) -> Optional[str]:
    """
    Create emergency replica in fastest-boot pool.

    Args:
        agent_id: Agent UUID
        reason: 'rebalance-recommendation' or 'termination-notice'
        deadline_seconds: Time until expected termination

    Returns:
        replica_id if created, None if failed
    """
    logger.warning(f"Creating EMERGENCY replica for {agent_id} (deadline: {deadline_seconds}s)")

    # Get agent details
    agent = execute_query(
        "SELECT * FROM agents WHERE id = %s",
        (agent_id,),
        fetch_one=True
    )

    if not agent:
        logger.error(f"Agent {agent_id} not found")
        return None

    # Select fastest boot pool
    fastest_pool = select_fastest_boot_pool(
        agent_id=agent_id,
        region=agent['region'],
        instance_type=agent['instance_type']
    )

    if not fastest_pool:
        logger.warning(f"No fastest pool found, using current pool")
        fastest_pool = agent['current_pool_id']

    # Create replica record
    replica_id = generate_uuid()

    try:
        execute_query("""
            INSERT INTO replica_instances
            (id, agent_id, instance_id, replica_type, pool_id, instance_type,
             region, az, status, created_at, emergency_creation, parent_instance_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'launching', NOW(), TRUE, %s)
        """, (
            replica_id,
            agent_id,
            f"emergency-{agent_id[:8]}",  # Placeholder until launched
            'automatic-termination' if reason == 'termination-notice' else 'automatic-rebalance',
            fastest_pool,
            agent['instance_type'],
            agent['region'],
            agent['az'],
            agent['instance_id']
        ), commit=True)

        logger.info(f"Emergency replica {replica_id} created in pool {fastest_pool}")

        # Update agent with fastest pool cache
        execute_query("""
            UPDATE agents
            SET fastest_boot_pool_id = %s
            WHERE id = %s
        """, (fastest_pool, agent_id), commit=True)

        return replica_id

    except Exception as e:
        logger.error(f"Failed to create emergency replica: {e}")
        return None


def select_fastest_boot_pool(
    agent_id: str,
    region: str,
    instance_type: str
) -> Optional[str]:
    """
    Select the pool with historically fastest boot time for emergency.

    Returns pool_id with best boot time metrics, or None if no data.
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
        logger.info(f"Fastest boot pool: {pool_stats['pool_id']} "
                   f"({pool_stats['avg_boot_time']}s avg, {pool_stats['sample_count']} samples)")
        return pool_stats['pool_id']

    # Fallback 1: Check spot_pools table for cached metrics
    cached_pool = execute_query("""
        SELECT id, avg_boot_time_seconds
        FROM spot_pools
        WHERE region = %s
            AND instance_type = %s
            AND avg_boot_time_seconds IS NOT NULL
            AND is_active = TRUE
        ORDER BY avg_boot_time_seconds ASC
        LIMIT 1
    """, (region, instance_type), fetch_one=True)

    if cached_pool:
        logger.info(f"Using cached fastest pool: {cached_pool['id']} "
                   f"({cached_pool['avg_boot_time_seconds']}s)")
        return cached_pool['id']

    # Fallback 2: Current pool
    agent = execute_query(
        "SELECT current_pool_id FROM agents WHERE id = %s",
        (agent_id,),
        fetch_one=True
    )

    if agent and agent['current_pool_id']:
        logger.info(f"No boot time data, using current pool: {agent['current_pool_id']}")
        return agent['current_pool_id']

    logger.warning("No pool selection data available")
    return None


def promote_replica(replica_id: str, emergency: bool = False) -> bool:
    """
    Promote replica to primary instance.

    Args:
        replica_id: Replica UUID to promote
        emergency: True if emergency promotion (skip some checks)

    Returns:
        True if promotion successful, False otherwise
    """
    logger.info(f"Promoting replica {replica_id} (emergency: {emergency})")

    # Get replica details
    replica = execute_query(
        "SELECT * FROM replica_instances WHERE id = %s",
        (replica_id,),
        fetch_one=True
    )

    if not replica:
        logger.error(f"Replica {replica_id} not found")
        return False

    # Verify replica is ready (skip in emergency)
    if not emergency and replica['status'] != 'ready':
        logger.error(f"Replica {replica_id} not ready (status: {replica['status']})")
        return False

    agent_id = replica['agent_id']

    # Start transaction for atomic promotion
    operations = [
        # Update replica status
        ("""UPDATE replica_instances
            SET status = 'promoted', promoted_at = NOW()
            WHERE id = %s""",
         (replica_id,)),

        # Demote old primary to zombie
        ("""UPDATE instances
            SET instance_status = 'zombie', is_primary = FALSE, terminated_at = NOW()
            WHERE agent_id = %s AND is_primary = TRUE AND instance_status = 'running_primary'""",
         (agent_id,)),

        # Create new primary instance record
        ("""INSERT INTO instances
            (id, client_id, agent_id, instance_type, region, az,
             current_mode, current_pool_id, is_primary, instance_status, installed_at)
            SELECT %s, (SELECT client_id FROM agents WHERE id = %s), %s,
                   instance_type, region, az, 'spot', pool_id, TRUE, 'running_primary', NOW()
            FROM replica_instances WHERE id = %s""",
         (replica['instance_id'], agent_id, agent_id, replica_id))
    ]

    success = execute_transaction(operations)

    if success:
        logger.info(f"✓ Replica {replica_id} promoted to primary")

        # Log system event
        log_system_event(
            'replica_promoted',
            'info',
            f"Replica {replica_id} promoted to primary",
            agent_id=agent_id,
            metadata={'replica_id': replica_id, 'emergency': emergency}
        )

        return True
    else:
        logger.error(f"Failed to promote replica {replica_id}")
        return False


def verify_replica_health(replica_id: str) -> Dict:
    """
    Verify replica health before promotion.

    Returns:
        dict with keys: healthy (bool), reason (str), checks (dict)
    """
    replica = execute_query(
        "SELECT * FROM replica_instances WHERE id = %s",
        (replica_id,),
        fetch_one=True
    )

    if not replica:
        return {'healthy': False, 'reason': 'Replica not found', 'checks': {}}

    checks = {
        'status_ready': replica['status'] == 'ready',
        'sync_completed': replica['sync_status'] == 'synced',
        'sync_recent': False,
        'no_errors': not replica.get('error_message')
    }

    # Check if sync is recent (within last 60 seconds)
    if replica['last_sync_at']:
        from datetime import datetime
        age_seconds = (datetime.now() - replica['last_sync_at']).total_seconds()
        checks['sync_recent'] = age_seconds < 60

    all_checks_passed = all(checks.values())

    return {
        'healthy': all_checks_passed,
        'reason': 'All checks passed' if all_checks_passed else 'Some checks failed',
        'checks': checks,
        'replica': replica
    }
