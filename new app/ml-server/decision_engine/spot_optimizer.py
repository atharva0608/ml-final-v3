"""
Spot Optimizer Engine

Select optimal Spot instances using AWS Spot Advisor data (NOT SPS scores)

Data Sources:
- AWS Spot Advisor JSON: https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json
- Historical Spot prices from database
- On-Demand prices from database

Risk Score Formula (0.0 = unsafe, 1.0 = safe):
  Risk Score = (0.60 × Public_Rate_Score) +
               (0.25 × Volatility_Score) +
               (0.10 × Gap_Score) +
               (0.05 × Time_Score)
"""

from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime
import logging

from .base_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)


class SpotOptimizerEngine(BaseDecisionEngine):
    """
    Spot Instance Optimizer

    Uses AWS Spot Advisor public data to select optimal Spot instances
    with lowest interruption risk and highest savings potential.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.interruption_rate_scores = {
            "<5%": 1.0,
            "5-10%": 0.8,
            "10-15%": 0.6,
            "15-20%": 0.4,
            ">20%": 0.2
        }

    def decide(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate Spot instance optimization recommendations

        Args:
            cluster_state: Current cluster state with nodes and metrics
            requirements:
                - cpu: Required CPU cores
                - memory: Required memory (GB)
                - region: AWS region
                - workload_type: Type of workload (stateless, stateful, batch)
            constraints:
                - max_interruption_risk: Maximum acceptable risk (0.0-1.0)
                - preferred_families: List of instance families (e.g., ['m5', 'c5'])
                - exclude_instances: List of instances to exclude

        Returns:
            Decision response with Spot recommendations
        """
        self.validate_input(cluster_state)
        logger.info("Generating Spot optimization recommendations")

        constraints = constraints or {}
        max_risk = constraints.get("max_interruption_risk", 0.15)
        preferred_families = constraints.get("preferred_families", [])

        # Extract requirements
        required_cpu = requirements.get("cpu", 2)
        required_memory = requirements.get("memory", 4)
        region = requirements.get("region", "us-east-1")
        workload_type = requirements.get("workload_type", "stateless")

        # TODO: Query database for:
        # 1. Spot Advisor data for region
        # 2. Historical Spot prices (last 7 days)
        # 3. On-Demand prices

        # For now, use sample data (Day Zero fallback)
        candidate_instances = self._get_candidate_instances(
            required_cpu,
            required_memory,
            region,
            preferred_families
        )

        # Score each candidate
        scored_instances = []
        for instance in candidate_instances:
            risk_score = self._calculate_risk_score(instance)
            savings_pct = self._calculate_savings(instance)

            if risk_score >= (1.0 - max_risk):  # Filter by risk threshold
                scored_instances.append({
                    "instance_type": instance["type"],
                    "risk_score": risk_score,
                    "interruption_probability": 1.0 - risk_score,
                    "savings_percentage": savings_pct,
                    "estimated_monthly_cost": instance["spot_price"] * 730,  # hours/month
                    "on_demand_monthly_cost": instance["od_price"] * 730,
                    "monthly_savings": (instance["od_price"] - instance["spot_price"]) * 730
                })

        # Sort by risk score (descending) and savings (descending)
        scored_instances.sort(
            key=lambda x: (x["risk_score"], x["savings_percentage"]),
            reverse=True
        )

        # Take top 5 recommendations
        recommendations = scored_instances[:5]

        # Calculate total estimated savings
        if recommendations:
            estimated_savings = Decimal(recommendations[0]["monthly_savings"])
        else:
            estimated_savings = Decimal(0)

        # Build execution plan
        execution_plan = self._build_execution_plan(recommendations, workload_type)

        # Create response
        return self.create_response(
            recommendations=recommendations,
            confidence_score=0.95 if recommendations else 0.5,
            estimated_savings=estimated_savings,
            execution_plan=execution_plan,
            metadata={
                "region": region,
                "workload_type": workload_type,
                "candidates_evaluated": len(candidate_instances),
                "risk_threshold": max_risk
            }
        )

    def _get_candidate_instances(
        self,
        cpu: float,
        memory: float,
        region: str,
        preferred_families: List[str]
    ) -> List[Dict[str, Any]]:
        """Get candidate instances matching requirements"""
        # Sample data (replace with database query)
        candidates = [
            {"type": "m5.large", "cpu": 2, "memory": 8, "spot_price": 0.03, "od_price": 0.096, "interruption_rate": "<5%"},
            {"type": "c5.large", "cpu": 2, "memory": 4, "spot_price": 0.035, "od_price": 0.085, "interruption_rate": "5-10%"},
            {"type": "r5.large", "cpu": 2, "memory": 16, "spot_price": 0.045, "od_price": 0.126, "interruption_rate": "<5%"},
        ]

        # Filter by CPU and memory requirements
        filtered = [
            c for c in candidates
            if c["cpu"] >= cpu and c["memory"] >= memory
        ]

        # Filter by preferred families
        if preferred_families:
            filtered = [
                c for c in filtered
                if any(c["type"].startswith(f) for f in preferred_families)
            ]

        return filtered

    def _calculate_risk_score(self, instance: Dict[str, Any]) -> float:
        """
        Calculate risk score using AWS Spot Advisor data

        Risk Score = (0.60 × Public_Rate_Score) +
                     (0.25 × Volatility_Score) +
                     (0.10 × Gap_Score) +
                     (0.05 × Time_Score)
        """
        # Public rate score (from Spot Advisor)
        interruption_rate = instance.get("interruption_rate", "15-20%")
        public_rate_score = self.interruption_rate_scores.get(interruption_rate, 0.5)

        # Volatility score (placeholder - calculate from price history)
        volatility_score = 0.85  # TODO: Calculate from historical prices

        # Gap score (current price vs On-Demand)
        spot_price = instance.get("spot_price", 0.05)
        od_price = instance.get("od_price", 0.1)
        gap_score = 1.0 - (spot_price / od_price) if od_price > 0 else 0.5

        # Time score (placeholder - check current hour)
        time_score = 0.9  # TODO: Check if off-peak hours

        risk_score = (
            0.60 * public_rate_score +
            0.25 * volatility_score +
            0.10 * gap_score +
            0.05 * time_score
        )

        return round(risk_score, 4)

    def _calculate_savings(self, instance: Dict[str, Any]) -> float:
        """Calculate savings percentage vs On-Demand"""
        spot = instance.get("spot_price", 0)
        od = instance.get("od_price", 1)
        if od > 0:
            return round((1 - spot / od) * 100, 2)
        return 0.0

    def _build_execution_plan(
        self,
        recommendations: List[Dict[str, Any]],
        workload_type: str
    ) -> List[Dict[str, Any]]:
        """Build step-by-step execution plan"""
        if not recommendations:
            return []

        top_recommendation = recommendations[0]

        if workload_type == "stateless":
            return [
                {
                    "step": 1,
                    "action": "launch_spot_instance",
                    "instance_type": top_recommendation["instance_type"],
                    "description": f"Launch Spot instance {top_recommendation['instance_type']}"
                },
                {
                    "step": 2,
                    "action": "wait_for_ready",
                    "timeout_seconds": 120,
                    "description": "Wait for node to be ready"
                },
                {
                    "step": 3,
                    "action": "migrate_pods",
                    "description": "Migrate pods to new Spot instance"
                },
                {
                    "step": 4,
                    "action": "drain_old_node",
                    "description": "Drain old On-Demand node"
                },
                {
                    "step": 5,
                    "action": "terminate_old_node",
                    "description": "Terminate old On-Demand instance"
                }
            ]
        else:
            return [
                {
                    "step": 1,
                    "action": "evaluate_risk",
                    "description": "Evaluate interruption risk for stateful workload"
                },
                {
                    "step": 2,
                    "action": "manual_approval",
                    "description": "Require manual approval for stateful workload migration"
                }
            ]
