"""
CloudOptim Control Plane - Safe Executor
========================================

Purpose: Wraps ALL ML Server calls with mandatory safety validation
Author: Architecture Team
Date: 2025-12-01

Integration Pattern: Safety-First Execution
- ALL optimization requests MUST flow through SafeExecutor
- NO direct calls to ML Server allowed (prevents safety bypass)
- SafetyEnforcer validates BEFORE execution
- Execution only proceeds if safety constraints pass

Flow:
1. Request optimization from ML Server
2. Validate recommendation with SafetyEnforcer (NEW - CRITICAL LAYER)
3. If violations detected:
   a. Try to create safe alternative
   b. If safe alternative exists → execute it
   c. If no safe alternative → REJECT (log violation, return error)
4. Execute safe recommendation via AWS APIs
5. Track results in database

This is the PRIMARY integration point between ML Server and Core Platform.
Before: Direct ml_client calls → Unsafe execution
After:  SafeExecutor → Safety validation → Safe execution

Usage:
    executor = SafeExecutor(db_session, ml_client, k8s_client, aws_client)
    result = await executor.execute_optimization(
        cluster_id=cluster_id,
        optimization_type='spot_optimize',
        requirements={'target_capacity': 100}
    )

    if result['success']:
        # Safe recommendation executed
        logger.info(f"Deployed {result['pools_deployed']} pools")
    else:
        # Rejected due to safety violations
        logger.error(f"Rejected: {result['violations']}")
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from .safety_enforcer import SafetyEnforcer, SafetyConstraintViolation
from ..clients.ml_client import MLServerClient
from ..clients.k8s_client import KubernetesClient
from ..clients.aws_client import AWSClient


logger = logging.getLogger(__name__)


class SafeExecutor:
    """
    Safe Executor - Wraps ML Server calls with mandatory safety validation

    This class ensures that ALL ML recommendations are validated against
    safety constraints BEFORE execution. This prevents:
    - Deploying to high-risk Spot pools
    - Over-concentration in single pool
    - Insufficient geographic diversity
    - No fallback capacity

    Key Principle: NEVER execute unsafe recommendations, even if ML confidence is high.
    """

    def __init__(
        self,
        db: AsyncSession,
        ml_client: MLServerClient,
        k8s_client: KubernetesClient,
        aws_client: AWSClient
    ):
        """
        Initialize SafeExecutor

        Args:
            db: Database session
            ml_client: ML Server client for decision requests
            k8s_client: Kubernetes API client for pod/node operations
            aws_client: AWS API client for EC2/Spot operations
        """
        self.db = db
        self.ml_client = ml_client
        self.k8s_client = k8s_client
        self.aws_client = aws_client
        self.safety_enforcer = SafetyEnforcer(db)
        self.logger = logging.getLogger(f"{__name__}.SafeExecutor")

    async def execute_optimization(
        self,
        cluster_id: UUID,
        optimization_type: str,
        requirements: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute optimization with mandatory safety validation

        Args:
            cluster_id: UUID of target cluster
            optimization_type: Type of optimization
                - 'spot_optimize': Spot instance optimization
                - 'bin_pack': Bin packing / node consolidation
                - 'rightsize': Rightsizing recommendations
                - 'schedule': Office hours scheduling
            requirements: Optimization requirements dict
            constraints: Additional constraints dict

        Returns:
            {
                'success': bool,
                'optimization_type': str,
                'recommendation': Dict (if successful),
                'execution_result': Dict (AWS/K8s operation results),
                'safety_validation': Dict (SafetyEnforcer results),
                'violations': List[str] (if any),
                'action_taken': str,
                'metadata': Dict
            }
        """
        self.logger.info(
            f"Executing {optimization_type} for cluster {cluster_id} "
            f"with requirements: {requirements}"
        )

        try:
            # Step 1: Get recommendation from ML Server
            ml_recommendation = await self._request_ml_decision(
                cluster_id=cluster_id,
                optimization_type=optimization_type,
                requirements=requirements,
                constraints=constraints
            )

            if not ml_recommendation or not ml_recommendation.get('success'):
                return {
                    'success': False,
                    'optimization_type': optimization_type,
                    'error': 'ML Server failed to provide recommendation',
                    'ml_response': ml_recommendation
                }

            # Step 2: SAFETY VALIDATION (CRITICAL - NEW LAYER)
            self.logger.info(f"Validating ML recommendation with SafetyEnforcer...")

            safety_result = await self.safety_enforcer.validate_recommendation(
                cluster_id=cluster_id,
                recommendation=ml_recommendation['recommendation']
            )

            # Step 3: Decision based on safety validation
            if safety_result['is_safe']:
                # ✅ Safe recommendation - proceed with execution
                self.logger.info(
                    f"✓ Recommendation APPROVED for cluster {cluster_id} "
                    f"(action: {safety_result['action_taken']})"
                )

                # Execute safe recommendation
                execution_result = await self._execute_recommendation(
                    cluster_id=cluster_id,
                    recommendation=safety_result['recommendation'],
                    optimization_type=optimization_type
                )

                return {
                    'success': True,
                    'optimization_type': optimization_type,
                    'recommendation': safety_result['recommendation'],
                    'execution_result': execution_result,
                    'safety_validation': safety_result,
                    'violations': safety_result.get('violations', []),
                    'action_taken': safety_result['action_taken'],
                    'metadata': {
                        'was_modified': safety_result['action_taken'] == 'created_safe_alternative',
                        'original_recommendation': (
                            safety_result['metadata'].get('original_recommendation')
                            if safety_result['action_taken'] == 'created_safe_alternative'
                            else None
                        ),
                        'execution_timestamp': datetime.utcnow().isoformat()
                    }
                }

            else:
                # ❌ Unsafe recommendation - REJECT
                self.logger.error(
                    f"✗ Recommendation REJECTED for cluster {cluster_id} - "
                    f"safety violations detected: {len(safety_result['violations'])} violations"
                )

                return {
                    'success': False,
                    'optimization_type': optimization_type,
                    'recommendation': None,
                    'execution_result': None,
                    'safety_validation': safety_result,
                    'violations': safety_result['violations'],
                    'action_taken': 'rejected',
                    'error': 'Safety constraint violations - cannot execute',
                    'metadata': {
                        'violation_type': safety_result['violation_type'],
                        'rejection_reason': safety_result['metadata'].get('rejection_reason'),
                        'original_recommendation': safety_result['metadata'].get('original_recommendation')
                    }
                }

        except SafetyConstraintViolation as e:
            # Safety constraint violation exception
            self.logger.error(
                f"Safety constraint violation for cluster {cluster_id}: {e.message}"
            )

            return {
                'success': False,
                'optimization_type': optimization_type,
                'error': f"Safety constraint violation: {e.message}",
                'violations': e.violations,
                'violation_type': e.violation_type
            }

        except Exception as e:
            # Unexpected error
            self.logger.exception(
                f"Unexpected error executing optimization for cluster {cluster_id}: {e}"
            )

            return {
                'success': False,
                'optimization_type': optimization_type,
                'error': f"Execution failed: {str(e)}",
                'exception_type': type(e).__name__
            }

    async def _request_ml_decision(
        self,
        cluster_id: UUID,
        optimization_type: str,
        requirements: Optional[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Request decision from ML Server

        Args:
            cluster_id: UUID of target cluster
            optimization_type: Type of optimization
            requirements: Requirements dict
            constraints: Constraints dict

        Returns:
            ML Server response dict
        """
        # Get cluster state from Kubernetes API
        cluster_state = await self.k8s_client.get_cluster_state(cluster_id)

        # Map optimization type to ML Server endpoint
        endpoint_map = {
            'spot_optimize': '/api/v1/ml/decision/spot-optimize',
            'bin_pack': '/api/v1/ml/decision/bin-pack',
            'rightsize': '/api/v1/ml/decision/rightsize',
            'schedule': '/api/v1/ml/decision/schedule',
            'ghost_probe': '/api/v1/ml/decision/ghost-probe',
            'volume_cleanup': '/api/v1/ml/decision/volume-cleanup',
            'network_optimize': '/api/v1/ml/decision/network-optimize',
            'oomkilled_remediate': '/api/v1/ml/decision/oomkilled-remediate'
        }

        endpoint = endpoint_map.get(optimization_type)
        if not endpoint:
            raise ValueError(f"Unknown optimization type: {optimization_type}")

        # Request decision from ML Server
        response = await self.ml_client.post(
            endpoint=endpoint,
            data={
                'cluster_id': str(cluster_id),
                'cluster_state': cluster_state,
                'requirements': requirements or {},
                'constraints': constraints or {}
            }
        )

        return response

    async def _execute_recommendation(
        self,
        cluster_id: UUID,
        recommendation: Dict[str, Any],
        optimization_type: str
    ) -> Dict[str, Any]:
        """
        Execute validated recommendation via AWS APIs and Kubernetes

        Args:
            cluster_id: UUID of target cluster
            recommendation: Validated safe recommendation
            optimization_type: Type of optimization

        Returns:
            Execution result dict with:
            - pools_deployed: List of deployed pools
            - instances_launched: List of launched instances
            - k8s_updates: Kubernetes resource updates
            - errors: Any errors encountered
        """
        self.logger.info(
            f"Executing safe recommendation for cluster {cluster_id}: "
            f"{len(recommendation.get('pools', []))} pools, "
            f"{recommendation.get('on_demand_count', 0)} On-Demand instances"
        )

        pools_deployed = []
        instances_launched = []
        k8s_updates = []
        errors = []

        try:
            # Deploy Spot pools
            for pool in recommendation.get('pools', []):
                try:
                    # Launch Spot instances via AWS API
                    spot_result = await self.aws_client.launch_spot_instances(
                        instance_type=pool['instance_type'],
                        availability_zone=pool['availability_zone'],
                        count=pool['allocation_count'],
                        cluster_id=str(cluster_id)
                    )

                    if spot_result['success']:
                        pools_deployed.append(pool)
                        instances_launched.extend(spot_result['instance_ids'])

                        self.logger.info(
                            f"✓ Deployed pool {pool['instance_type']}:{pool['availability_zone']} "
                            f"({pool['allocation_count']} instances, risk={pool['risk_score']:.3f})"
                        )
                    else:
                        errors.append({
                            'pool': pool,
                            'error': spot_result.get('error', 'Unknown error')
                        })

                except Exception as e:
                    self.logger.error(f"Failed to deploy pool {pool}: {e}")
                    errors.append({'pool': pool, 'error': str(e)})

            # Deploy On-Demand buffer (if specified)
            on_demand_count = recommendation.get('on_demand_count', 0)
            if on_demand_count > 0:
                try:
                    od_result = await self.aws_client.launch_on_demand_instances(
                        instance_type=recommendation.get('on_demand_instance_type', 'm5.large'),
                        count=on_demand_count,
                        cluster_id=str(cluster_id)
                    )

                    if od_result['success']:
                        instances_launched.extend(od_result['instance_ids'])
                        self.logger.info(
                            f"✓ Deployed On-Demand buffer ({on_demand_count} instances)"
                        )

                except Exception as e:
                    self.logger.error(f"Failed to deploy On-Demand buffer: {e}")
                    errors.append({'type': 'on_demand', 'error': str(e)})

            # Update Kubernetes cluster autoscaler (if needed)
            if optimization_type in ['spot_optimize', 'bin_pack']:
                try:
                    k8s_result = await self.k8s_client.update_cluster_autoscaler(
                        cluster_id=cluster_id,
                        node_pools=pools_deployed
                    )

                    k8s_updates.append(k8s_result)

                except Exception as e:
                    self.logger.error(f"Failed to update Kubernetes: {e}")
                    errors.append({'type': 'kubernetes', 'error': str(e)})

            return {
                'pools_deployed': pools_deployed,
                'instances_launched': instances_launched,
                'k8s_updates': k8s_updates,
                'errors': errors,
                'success': len(errors) == 0,
                'execution_timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.exception(f"Execution failed: {e}")
            return {
                'pools_deployed': pools_deployed,
                'instances_launched': instances_launched,
                'k8s_updates': k8s_updates,
                'errors': errors + [{'type': 'execution', 'error': str(e)}],
                'success': False,
                'execution_timestamp': datetime.utcnow().isoformat()
            }

    async def execute_spot_optimization(
        self,
        cluster_id: UUID,
        target_capacity: int
    ) -> Dict[str, Any]:
        """
        Convenience method for Spot instance optimization

        Args:
            cluster_id: UUID of target cluster
            target_capacity: Target total capacity

        Returns:
            Execution result dict
        """
        return await self.execute_optimization(
            cluster_id=cluster_id,
            optimization_type='spot_optimize',
            requirements={'target_capacity': target_capacity}
        )

    async def execute_bin_packing(
        self,
        cluster_id: UUID
    ) -> Dict[str, Any]:
        """
        Convenience method for bin packing optimization

        Args:
            cluster_id: UUID of target cluster

        Returns:
            Execution result dict
        """
        return await self.execute_optimization(
            cluster_id=cluster_id,
            optimization_type='bin_pack'
        )

    async def execute_rightsizing(
        self,
        cluster_id: UUID,
        workload_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Convenience method for rightsizing optimization

        Args:
            cluster_id: UUID of target cluster
            workload_ids: Optional list of specific workload IDs to rightsize

        Returns:
            Execution result dict
        """
        return await self.execute_optimization(
            cluster_id=cluster_id,
            optimization_type='rightsize',
            requirements={'workload_ids': workload_ids} if workload_ids else {}
        )
