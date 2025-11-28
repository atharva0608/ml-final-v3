"""
Ghost Probe Scanner Engine

Detect zombie EC2 instances not in Kubernetes clusters
Day Zero compatible - works immediately without historical data
"""

from typing import Dict, Any, List
from decimal import Decimal
import logging

from .base_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)


class GhostProbeScanner(BaseDecisionEngine):
    """
    Ghost Probe Scanner

    Identifies EC2 instances running in customer account but NOT in K8s cluster
    These are "zombie" instances left behind after cluster operations
    """

    def decide(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Scan for ghost instances"""
        logger.info("Scanning for ghost EC2 instances")

        # Get lists from requirements (sent by Core Platform)
        ec2_instances = set(requirements.get("ec2_instances", []))
        k8s_nodes = set(requirements.get("k8s_node_instance_ids", []))
        ignored_tags = requirements.get("ignored_tags", ["cloudoptim:ignore"])

        # Find ghost instances: EC2 running but NOT in K8s
        ghost_instances = ec2_instances - k8s_nodes

        logger.info(f"Found {len(ghost_instances)} potential ghost instances")

        # Build recommendations
        recommendations = []
        for instance_id in ghost_instances:
            recommendations.append({
                "instance_id": instance_id,
                "status": "ghost",
                "action": "terminate",
                "grace_period_hours": 24,
                "requires_approval": True
            })

        # Estimate savings ($100/instance/month average)
        estimated_savings = Decimal(len(ghost_instances) * 100)

        execution_plan = self._build_execution_plan(len(ghost_instances))

        return self.create_response(
            recommendations=recommendations,
            confidence_score=0.95 if ghost_instances else 1.0,
            estimated_savings=estimated_savings,
            execution_plan=execution_plan,
            metadata={
                "total_ec2_instances": len(ec2_instances),
                "total_k8s_nodes": len(k8s_nodes),
                "ghost_instances_found": len(ghost_instances)
            }
        )

    def _build_execution_plan(self, ghost_count: int) -> List[Dict]:
        """Build execution plan for ghost cleanup"""
        if ghost_count == 0:
            return []

        return [
            {"step": 1, "action": "tag_instances", "description": "Tag ghost instances for review"},
            {"step": 2, "action": "wait_grace_period", "hours": 24, "description": "Wait 24-hour grace period"},
            {"step": 3, "action": "manual_approval", "description": "Require manual approval"},
            {"step": 4, "action": "terminate_instances", "description": "Terminate approved ghost instances"}
        ]
