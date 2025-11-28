"""
OOMKilled Auto-Remediation Engine

Detect OOMKilled pods and automatically increase memory limits
"""

from typing import Dict, Any, List
from decimal import Decimal
import logging

from .base_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)


class OOMKilledRemediationEngine(BaseDecisionEngine):
    """
    OOMKilled Auto-Remediation Engine

    Detects pods killed due to out-of-memory errors
    Automatically increases memory requests/limits to prevent future crashes
    """

    MEMORY_INCREASE_FACTOR = 1.5  # Increase by 50%
    MAX_INCREASE_FACTOR = 2.0  # Maximum 2x increase

    def decide(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Generate OOMKilled remediation recommendations"""
        logger.info("Analyzing OOMKilled pod events")

        # Get pod events from requirements (last 24 hours)
        pod_events = requirements.get("pod_events", [])

        # Filter OOMKilled events
        oomkilled_events = [
            e for e in pod_events
            if e.get("reason") == "OOMKilled"
        ]

        # Group by deployment
        oomkilled_by_deployment = {}
        for event in oomkilled_events:
            deployment = event.get("deployment")
            if deployment not in oomkilled_by_deployment:
                oomkilled_by_deployment[deployment] = []
            oomkilled_by_deployment[deployment].append(event)

        # Build recommendations
        recommendations = []
        for deployment, events in oomkilled_by_deployment.items():
            # Get current memory limit
            current_memory_mb = events[0].get("current_memory_mb", 512)

            # Calculate recommended memory (increase by 50%)
            recommended_memory_mb = int(current_memory_mb * self.MEMORY_INCREASE_FACTOR)

            # Cap at 2x original
            max_memory_mb = int(current_memory_mb * self.MAX_INCREASE_FACTOR)
            recommended_memory_mb = min(recommended_memory_mb, max_memory_mb)

            recommendations.append({
                "deployment": deployment,
                "namespace": events[0].get("namespace", "default"),
                "current_memory_mb": current_memory_mb,
                "recommended_memory_mb": recommended_memory_mb,
                "oomkilled_count": len(events),
                "action": "update_memory_limit" if len(events) < 3 else "manual_review"
            })

        # No direct savings (prevents downtime costs)
        estimated_savings = Decimal(0)

        execution_plan = self._build_execution_plan(recommendations)

        return self.create_response(
            recommendations=recommendations,
            confidence_score=0.9,
            estimated_savings=estimated_savings,
            execution_plan=execution_plan,
            metadata={
                "total_oomkilled_events": len(oomkilled_events),
                "affected_deployments": len(recommendations)
            }
        )

    def _build_execution_plan(self, recommendations: List[Dict]) -> List[Dict]:
        """Build execution plan for OOMKilled remediation"""
        if not recommendations:
            return []

        return [
            {"step": 1, "action": "update_deployments", "description": "Update memory limits in deployment specs"},
            {"step": 2, "action": "rolling_restart", "description": "Rolling restart to apply new limits"},
            {"step": 3, "action": "monitor_pods", "duration_hours": 24, "description": "Monitor for 24 hours to verify fix"}
        ]
