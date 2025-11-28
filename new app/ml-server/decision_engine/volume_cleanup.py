"""
Zombie Volume Cleanup Engine

Identify and remove unattached EBS volumes
"""

from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime, timedelta
import logging

from .base_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)


class VolumeCleanupEngine(BaseDecisionEngine):
    """
    Zombie Volume Cleanup Engine

    Identifies unattached EBS volumes and recommends deletion after grace period
    Typical savings: 5-10% of storage costs
    """

    GRACE_PERIOD_DAYS = 7

    def decide(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Scan for zombie volumes"""
        logger.info("Scanning for zombie EBS volumes")

        # Get volume list from requirements (sent by Core Platform)
        all_volumes = requirements.get("ebs_volumes", [])

        # Filter unattached volumes
        unattached = [
            v for v in all_volumes
            if v.get("status") == "available"  # available = unattached
        ]

        # Filter by age (>7 days unattached)
        cutoff_date = datetime.utcnow() - timedelta(days=self.GRACE_PERIOD_DAYS)
        zombie_volumes = [
            v for v in unattached
            if datetime.fromisoformat(v.get("last_attach_time", "2000-01-01")) < cutoff_date
        ]

        # Build recommendations
        recommendations = []
        total_size_gb = 0
        for volume in zombie_volumes:
            size_gb = volume.get("size_gb", 0)
            total_size_gb += size_gb
            recommendations.append({
                "volume_id": volume.get("volume_id"),
                "size_gb": size_gb,
                "age_days": (datetime.utcnow() - datetime.fromisoformat(volume.get("last_attach_time", "2000-01-01"))).days,
                "action": "delete",
                "requires_snapshot": volume.get("has_snapshots", False)
            })

        # Estimate savings ($0.10/GB/month for EBS)
        estimated_savings = Decimal(total_size_gb * 0.10)

        execution_plan = self._build_execution_plan(len(zombie_volumes))

        return self.create_response(
            recommendations=recommendations,
            confidence_score=0.9,
            estimated_savings=estimated_savings,
            execution_plan=execution_plan,
            metadata={
                "total_volumes": len(all_volumes),
                "zombie_volumes": len(zombie_volumes),
                "total_size_gb": total_size_gb
            }
        )

    def _build_execution_plan(self, volume_count: int) -> List[Dict]:
        """Build execution plan for volume cleanup"""
        if volume_count == 0:
            return []

        return [
            {"step": 1, "action": "tag_volumes", "description": "Tag zombie volumes for deletion"},
            {"step": 2, "action": "create_snapshots", "description": "Create snapshots if needed"},
            {"step": 3, "action": "manual_approval", "description": "Require manual approval"},
            {"step": 4, "action": "delete_volumes", "description": "Delete approved volumes"}
        ]
