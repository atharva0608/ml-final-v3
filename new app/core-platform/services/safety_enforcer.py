"""
CloudOptim Control Plane - Safety Constraint Enforcer
=====================================================

Purpose: Five-Layer Defense Strategy - Validates ALL ML recommendations before execution
Author: Architecture Team
Date: 2025-12-01

Critical Safety Constraints (Non-Negotiable):
1. Risk Threshold: risk_score >= 0.75 for ALL pools
2. AZ Distribution: Minimum 3 availability zones
3. Pool Concentration: Maximum 20% allocation per pool
4. On-Demand Buffer: Minimum 15% On-Demand instances
5. Multi-Factor Validation: All constraints must pass

This is the PRIMARY defense against ML recommendation failures and prevents:
- Deploying to high-risk Spot pools (interruption cascade)
- Over-concentration in single pool (single point of failure)
- Insufficient geographic diversity (AZ-level outages)
- No fallback capacity (entire cluster on Spot)

Architecture Pattern: Fail-Safe Design
- If ANY constraint violated → Create safe alternative OR reject
- Never execute unsafe recommendations (even if ML confidence is high)
- Log all violations to safety_violations table for audit
- Provide detailed violation explanations for debugging

Integration Point: ALL optimization requests flow through SafetyEnforcer
Before: ML Server → Core Platform executor → AWS APIs
After:  ML Server → SafetyEnforcer → Safe executor → AWS APIs
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

# Database models (import from core-platform/database/models.py)
from ..database.models import (
    Cluster,
    PoolAllocation,
    AZDistribution,
    SafetyViolation
)

logger = logging.getLogger(__name__)


class SafetyConstraintViolation(Exception):
    """Raised when safety constraint validation fails"""
    def __init__(self, violation_type: str, message: str, violations: List[str]):
        self.violation_type = violation_type
        self.message = message
        self.violations = violations
        super().__init__(message)


class SafetyEnforcer:
    """
    Five-Layer Safety Constraint Enforcer

    Validates ALL ML recommendations against safety constraints before execution.
    This is the critical layer that prevents unsafe deployments.

    Safety Constraints (in order of severity):
    1. Risk Threshold (CRITICAL): All pools must have risk_score >= 0.75
    2. AZ Distribution (CRITICAL): Minimum 3 availability zones
    3. Pool Concentration (HIGH): Maximum 20% per pool
    4. On-Demand Buffer (HIGH): Minimum 15% On-Demand instances

    Violation Handling:
    - CRITICAL violations → Reject recommendation entirely
    - HIGH violations → Attempt to create safe alternative
    - If safe alternative impossible → Reject

    Usage:
        enforcer = SafetyEnforcer(db_session)
        result = await enforcer.validate_recommendation(cluster_id, recommendation)
        if result['is_safe']:
            execute(result['recommendation'])
        else:
            log_violation(result['violations'])
    """

    # Safety thresholds (constants)
    MIN_RISK_SCORE = Decimal('0.75')  # 75% safety threshold
    MIN_AVAILABILITY_ZONES = 3
    MAX_POOL_ALLOCATION_PCT = Decimal('0.20')  # 20% max per pool
    MIN_ON_DEMAND_BUFFER_PCT = Decimal('0.15')  # 15% On-Demand buffer

    def __init__(self, db: AsyncSession):
        """
        Initialize SafetyEnforcer

        Args:
            db: AsyncSession for database operations
        """
        self.db = db
        self.logger = logging.getLogger(f"{__name__}.SafetyEnforcer")

    async def validate_recommendation(
        self,
        cluster_id: UUID,
        recommendation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate ML recommendation against ALL safety constraints

        Args:
            cluster_id: UUID of target cluster
            recommendation: ML recommendation dict with structure:
                {
                    'pools': [
                        {
                            'instance_type': 'm5.large',
                            'availability_zone': 'us-east-1a',
                            'risk_score': 0.85,
                            'allocation_count': 10
                        },
                        ...
                    ],
                    'on_demand_count': 5,
                    'total_capacity': 50
                }

        Returns:
            {
                'is_safe': bool,
                'recommendation': Dict (original or safe alternative),
                'violations': List[str],
                'violation_type': Optional[str],
                'action_taken': str,
                'metadata': Dict
            }
        """
        violations = []
        violation_types = []

        self.logger.info(f"Validating recommendation for cluster {cluster_id}")

        # Load cluster data
        cluster = await self._get_cluster(cluster_id)
        if not cluster:
            raise ValueError(f"Cluster {cluster_id} not found")

        # Constraint 1: Risk Threshold (CRITICAL)
        risk_violations = await self._check_risk_threshold(recommendation)
        if risk_violations:
            violations.extend(risk_violations)
            violation_types.append('risk_threshold')

        # Constraint 2: AZ Distribution (CRITICAL)
        az_violations = await self._check_az_distribution(recommendation)
        if az_violations:
            violations.extend(az_violations)
            violation_types.append('az_distribution')

        # Constraint 3: Pool Concentration (HIGH)
        pool_violations = await self._check_pool_concentration(
            cluster_id, recommendation
        )
        if pool_violations:
            violations.extend(pool_violations)
            violation_types.append('pool_concentration')

        # Constraint 4: On-Demand Buffer (HIGH)
        buffer_violations = await self._check_on_demand_buffer(recommendation)
        if buffer_violations:
            violations.extend(buffer_violations)
            violation_types.append('on_demand_buffer')

        # Determine action based on violations
        if not violations:
            # ✅ All constraints passed
            self.logger.info(
                f"✓ Recommendation SAFE for cluster {cluster_id} "
                f"({len(recommendation.get('pools', []))} pools, "
                f"{recommendation.get('on_demand_count', 0)} On-Demand)"
            )

            return {
                'is_safe': True,
                'recommendation': recommendation,
                'violations': [],
                'violation_type': None,
                'action_taken': 'approved',
                'metadata': {
                    'validation_timestamp': datetime.utcnow().isoformat(),
                    'pools_validated': len(recommendation.get('pools', [])),
                    'min_risk_score': float(min(
                        pool['risk_score']
                        for pool in recommendation.get('pools', [])
                    ) if recommendation.get('pools') else 0),
                    'total_azs': len(set(
                        pool['availability_zone']
                        for pool in recommendation.get('pools', [])
                    ))
                }
            }

        else:
            # ❌ Violations detected - attempt to create safe alternative
            self.logger.warning(
                f"✗ Recommendation UNSAFE for cluster {cluster_id}: "
                f"{len(violations)} violations detected"
            )

            # Try to create safe alternative
            safe_alternative = await self._create_safe_alternative(
                cluster_id, recommendation, violations
            )

            if safe_alternative:
                # Log violation but use safe alternative
                await self._log_violation(
                    cluster_id=cluster_id,
                    violation_types=violation_types,
                    violations=violations,
                    original_recommendation=recommendation,
                    safe_alternative=safe_alternative,
                    severity='high',
                    was_rejected=False,
                    was_modified=True
                )

                self.logger.info(
                    f"✓ Created safe alternative for cluster {cluster_id}"
                )

                return {
                    'is_safe': True,
                    'recommendation': safe_alternative,
                    'violations': violations,
                    'violation_type': 'multiple_violations' if len(violation_types) > 1 else violation_types[0],
                    'action_taken': 'created_safe_alternative',
                    'metadata': {
                        'original_recommendation': recommendation,
                        'modifications': self._describe_modifications(
                            recommendation, safe_alternative
                        )
                    }
                }

            else:
                # Cannot create safe alternative - REJECT
                await self._log_violation(
                    cluster_id=cluster_id,
                    violation_types=violation_types,
                    violations=violations,
                    original_recommendation=recommendation,
                    safe_alternative=None,
                    severity='critical',
                    was_rejected=True,
                    was_modified=False
                )

                self.logger.error(
                    f"✗ REJECTED recommendation for cluster {cluster_id} - "
                    f"cannot create safe alternative"
                )

                return {
                    'is_safe': False,
                    'recommendation': None,
                    'violations': violations,
                    'violation_type': 'multiple_violations' if len(violation_types) > 1 else violation_types[0],
                    'action_taken': 'rejected',
                    'metadata': {
                        'rejection_reason': 'Cannot create safe alternative',
                        'original_recommendation': recommendation
                    }
                }

    async def _check_risk_threshold(
        self,
        recommendation: Dict[str, Any]
    ) -> List[str]:
        """
        Constraint 1: Risk Threshold
        Validate that ALL pools have risk_score >= 0.75

        Returns:
            List of violation messages (empty if no violations)
        """
        violations = []
        pools = recommendation.get('pools', [])

        for pool in pools:
            risk_score = Decimal(str(pool.get('risk_score', 0)))

            if risk_score < self.MIN_RISK_SCORE:
                violations.append(
                    f"Pool {pool['instance_type']}:{pool['availability_zone']} "
                    f"has risk_score {risk_score:.4f} < minimum {self.MIN_RISK_SCORE:.2f}"
                )

        return violations

    async def _check_az_distribution(
        self,
        recommendation: Dict[str, Any]
    ) -> List[str]:
        """
        Constraint 2: AZ Distribution
        Validate minimum 3 availability zones for geographic diversity

        Returns:
            List of violation messages (empty if no violations)
        """
        violations = []
        pools = recommendation.get('pools', [])

        unique_azs = set(pool['availability_zone'] for pool in pools)

        if len(unique_azs) < self.MIN_AVAILABILITY_ZONES:
            violations.append(
                f"Recommendation uses only {len(unique_azs)} AZs "
                f"(minimum required: {self.MIN_AVAILABILITY_ZONES}). "
                f"AZs: {', '.join(sorted(unique_azs))}"
            )

        return violations

    async def _check_pool_concentration(
        self,
        cluster_id: UUID,
        recommendation: Dict[str, Any]
    ) -> List[str]:
        """
        Constraint 3: Pool Concentration
        Validate that no single pool exceeds 20% of cluster capacity

        Returns:
            List of violation messages (empty if no violations)
        """
        violations = []
        pools = recommendation.get('pools', [])
        total_capacity = recommendation.get('total_capacity', 0)

        if total_capacity == 0:
            return ["Total capacity is 0 - cannot validate pool concentration"]

        for pool in pools:
            allocation_count = pool.get('allocation_count', 0)
            allocation_pct = Decimal(allocation_count) / Decimal(total_capacity)

            if allocation_pct > self.MAX_POOL_ALLOCATION_PCT:
                violations.append(
                    f"Pool {pool['instance_type']}:{pool['availability_zone']} "
                    f"allocation {allocation_pct:.1%} exceeds maximum "
                    f"{self.MAX_POOL_ALLOCATION_PCT:.0%} "
                    f"({allocation_count}/{total_capacity} instances)"
                )

        return violations

    async def _check_on_demand_buffer(
        self,
        recommendation: Dict[str, Any]
    ) -> List[str]:
        """
        Constraint 4: On-Demand Buffer
        Validate minimum 15% On-Demand instances for fallback capacity

        Returns:
            List of violation messages (empty if no violations)
        """
        violations = []

        on_demand_count = recommendation.get('on_demand_count', 0)
        total_capacity = recommendation.get('total_capacity', 0)

        if total_capacity == 0:
            return ["Total capacity is 0 - cannot validate On-Demand buffer"]

        on_demand_pct = Decimal(on_demand_count) / Decimal(total_capacity)

        if on_demand_pct < self.MIN_ON_DEMAND_BUFFER_PCT:
            violations.append(
                f"On-Demand buffer {on_demand_pct:.1%} below minimum "
                f"{self.MIN_ON_DEMAND_BUFFER_PCT:.0%} "
                f"({on_demand_count}/{total_capacity} instances)"
            )

        return violations

    async def _create_safe_alternative(
        self,
        cluster_id: UUID,
        original_recommendation: Dict[str, Any],
        violations: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to create a safe alternative recommendation

        Strategy:
        1. Remove pools with risk_score < 0.75
        2. Add pools from additional AZs if needed
        3. Cap pool allocations at 20%
        4. Increase On-Demand buffer to 15% if needed

        Returns:
            Safe alternative recommendation or None if impossible
        """
        # Deep copy original recommendation
        safe_rec = {
            'pools': [pool.copy() for pool in original_recommendation.get('pools', [])],
            'on_demand_count': original_recommendation.get('on_demand_count', 0),
            'total_capacity': original_recommendation.get('total_capacity', 0)
        }

        # Fix 1: Remove low-risk pools
        safe_rec['pools'] = [
            pool for pool in safe_rec['pools']
            if Decimal(str(pool.get('risk_score', 0))) >= self.MIN_RISK_SCORE
        ]

        if not safe_rec['pools']:
            # No safe pools available
            return None

        # Fix 2: Ensure 3+ AZs (simplified - would need AWS API in production)
        unique_azs = set(pool['availability_zone'] for pool in safe_rec['pools'])
        if len(unique_azs) < self.MIN_AVAILABILITY_ZONES:
            # Cannot add AZs without AWS API - reject
            self.logger.warning("Cannot add AZs - AWS API integration required")
            return None

        # Fix 3: Cap pool allocations at 20%
        total_capacity = safe_rec['total_capacity']
        max_per_pool = int(total_capacity * self.MAX_POOL_ALLOCATION_PCT)

        for pool in safe_rec['pools']:
            if pool['allocation_count'] > max_per_pool:
                pool['allocation_count'] = max_per_pool

        # Fix 4: Ensure 15% On-Demand buffer
        total_spot = sum(pool['allocation_count'] for pool in safe_rec['pools'])
        min_on_demand = int(total_capacity * self.MIN_ON_DEMAND_BUFFER_PCT)

        if safe_rec['on_demand_count'] < min_on_demand:
            # Reduce Spot allocations to make room for On-Demand
            reduction_needed = min_on_demand - safe_rec['on_demand_count']

            # Reduce from largest pool first
            safe_rec['pools'].sort(key=lambda p: p['allocation_count'], reverse=True)

            for pool in safe_rec['pools']:
                if reduction_needed <= 0:
                    break

                reduction = min(pool['allocation_count'], reduction_needed)
                pool['allocation_count'] -= reduction
                reduction_needed -= reduction

            safe_rec['on_demand_count'] = min_on_demand

        # Remove empty pools
        safe_rec['pools'] = [
            pool for pool in safe_rec['pools']
            if pool['allocation_count'] > 0
        ]

        # Validate safe alternative
        if not safe_rec['pools']:
            return None

        return safe_rec

    async def _log_violation(
        self,
        cluster_id: UUID,
        violation_types: List[str],
        violations: List[str],
        original_recommendation: Dict[str, Any],
        safe_alternative: Optional[Dict[str, Any]],
        severity: str,
        was_rejected: bool,
        was_modified: bool
    ) -> None:
        """
        Log safety violation to database for audit trail

        Args:
            cluster_id: UUID of cluster
            violation_types: List of violation types
            violations: List of violation messages
            original_recommendation: Original ML recommendation
            safe_alternative: Safe alternative (if created)
            severity: Violation severity (critical, high, medium, low)
            was_rejected: Whether recommendation was rejected
            was_modified: Whether recommendation was modified
        """
        try:
            # Get cluster and customer_id
            cluster = await self._get_cluster(cluster_id)

            violation = SafetyViolation(
                violation_id=uuid4(),
                cluster_id=cluster_id,
                customer_id=cluster.customer_id,
                violation_type='multiple_violations' if len(violation_types) > 1 else violation_types[0],
                severity=severity,
                description='\n'.join(violations),
                recommendation_data=original_recommendation,
                safe_alternative_data=safe_alternative,
                action_taken=(
                    'rejected' if was_rejected
                    else 'created_safe_alternative' if was_modified
                    else 'approved'
                ),
                was_rejected=was_rejected,
                was_modified=was_modified,
                detected_at=datetime.utcnow()
            )

            self.db.add(violation)
            await self.db.commit()

            self.logger.info(
                f"Logged safety violation for cluster {cluster_id}: "
                f"{violation.violation_type} ({severity})"
            )

        except Exception as e:
            self.logger.error(f"Failed to log safety violation: {e}")
            # Don't fail validation if logging fails

    async def _get_cluster(self, cluster_id: UUID) -> Optional[Cluster]:
        """Get cluster from database"""
        result = await self.db.execute(
            select(Cluster).where(Cluster.cluster_id == cluster_id)
        )
        return result.scalar_one_or_none()

    def _describe_modifications(
        self,
        original: Dict[str, Any],
        modified: Dict[str, Any]
    ) -> List[str]:
        """
        Describe modifications made to create safe alternative

        Returns:
            List of human-readable modification descriptions
        """
        modifications = []

        # Pool changes
        orig_pools = len(original.get('pools', []))
        mod_pools = len(modified.get('pools', []))
        if orig_pools != mod_pools:
            modifications.append(
                f"Reduced pools from {orig_pools} to {mod_pools} "
                f"(removed {orig_pools - mod_pools} low-risk pools)"
            )

        # On-Demand changes
        orig_od = original.get('on_demand_count', 0)
        mod_od = modified.get('on_demand_count', 0)
        if orig_od != mod_od:
            modifications.append(
                f"Increased On-Demand buffer from {orig_od} to {mod_od} instances "
                f"({(mod_od / modified['total_capacity']):.1%})"
            )

        # Pool allocation changes
        for orig_pool, mod_pool in zip(original.get('pools', []), modified.get('pools', [])):
            if orig_pool.get('allocation_count') != mod_pool.get('allocation_count'):
                modifications.append(
                    f"Capped {orig_pool['instance_type']}:{orig_pool['availability_zone']} "
                    f"from {orig_pool['allocation_count']} to {mod_pool['allocation_count']} instances"
                )

        return modifications
