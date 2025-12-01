"""
Spot Optimizer Engine

Select optimal Spot instances using AWS Spot Advisor data + Customer Feedback

Data Sources:
- AWS Spot Advisor JSON: https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json
- Historical Spot prices from database
- On-Demand prices from database
- Customer interruption feedback (risk_score_adjustments table)

Risk Score Formula (ADAPTIVE - 0.0 = unsafe, 1.0 = safe):

  Month 1-3 (0% customer weight):
    Risk Score = (0.60 × AWS_Spot_Advisor_Score) +
                 (0.30 × Volatility_Score) +
                 (0.10 × Structural_Score)

  Month 12+ (25% customer weight):
    Risk Score = (0.35 × AWS_Spot_Advisor_Score) +
                 (0.30 × Volatility_Score) +
                 (0.25 × Customer_Feedback_Score) +
                 (0.10 × Structural_Score)

Customer feedback weight grows from 0% → 25% over 12 months based on
data maturity (total instance-hours observed). This creates competitive moat.
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from .base_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)


class SpotOptimizerEngine(BaseDecisionEngine):
    """
    Spot Instance Optimizer

    Uses AWS Spot Advisor public data to select optimal Spot instances
    with lowest interruption risk and highest savings potential.
    """

    def __init__(self, config: Dict[str, Any] = None, db: Optional[AsyncSession] = None):
        super().__init__(config)
        self.db = db  # Database session for customer feedback queries
        self.interruption_rate_scores = {
            "<5%": 1.0,
            "5-10%": 0.8,
            "10-15%": 0.6,
            "15-20%": 0.4,
            ">20%": 0.2
        }
        self._customer_feedback_weight = None  # Cached weight

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

    async def _calculate_risk_score(self, instance: Dict[str, Any], region: str, availability_zone: str = None) -> float:
        """
        Calculate ADAPTIVE risk score using AWS Spot Advisor + Customer Feedback

        New Formula (Adaptive):
          Risk Score = ((0.60 - customer_weight) × AWS_Spot_Advisor_Score) +
                       ((0.30 - customer_weight) × Volatility_Score) +
                       (customer_weight × Customer_Feedback_Score) +
                       (0.10 × Structural_Score)

        Customer weight grows from 0% (Month 1) to 25% (Month 12+)

        Month 1: Risk = 60% AWS + 30% Volatility + 10% Structural
        Month 12: Risk = 35% AWS + 30% Volatility + 25% Customer + 10% Structural

        Args:
            instance: Instance data with type, prices, interruption rate
            region: AWS region (e.g., 'us-east-1')
            availability_zone: Optional AZ (e.g., 'us-east-1a')

        Returns:
            Risk score (0.0-1.0, higher = safer)
        """
        instance_type = instance.get("type")

        # Component 1: AWS Spot Advisor score (baseline)
        interruption_rate = instance.get("interruption_rate", "15-20%")
        aws_spot_advisor_score = self.interruption_rate_scores.get(interruption_rate, 0.5)

        # Component 2: Volatility score (price stability)
        volatility_score = 0.85  # TODO: Calculate from historical price data

        # Component 3: Structural score (gap + time factors)
        spot_price = instance.get("spot_price", 0.05)
        od_price = instance.get("od_price", 0.1)
        gap_score = 1.0 - (spot_price / od_price) if od_price > 0 else 0.5

        time_score = self._get_time_score()  # Off-peak = higher score
        structural_score = (0.7 * gap_score) + (0.3 * time_score)

        # Component 4: Customer Feedback score (ADAPTIVE - grows over time)
        customer_feedback_score = aws_spot_advisor_score  # Default fallback
        customer_weight = await self._get_customer_feedback_weight()

        if self.db and customer_weight > 0:
            # Query risk_score_adjustments table for learned risk score
            learned_score = await self._get_learned_risk_score(
                instance_type=instance_type,
                region=region,
                availability_zone=availability_zone or f"{region}a"  # Default AZ
            )

            if learned_score is not None:
                customer_feedback_score = float(learned_score)
                logger.debug(
                    f"Using learned risk score for {instance_type}:{region}: "
                    f"base={aws_spot_advisor_score:.3f}, learned={customer_feedback_score:.3f}, "
                    f"weight={customer_weight:.2%}"
                )

        # Calculate final adaptive risk score
        final_risk_score = (
            (0.60 - customer_weight) * aws_spot_advisor_score +
            (0.30 - customer_weight) * volatility_score +
            customer_weight * customer_feedback_score +
            0.10 * structural_score
        )

        # Ensure score is in valid range
        final_risk_score = max(0.0, min(1.0, final_risk_score))

        logger.debug(
            f"Risk score for {instance_type}: {final_risk_score:.4f} "
            f"(AWS={aws_spot_advisor_score:.2f}, Volatility={volatility_score:.2f}, "
            f"Customer={customer_feedback_score:.2f} @{customer_weight:.2%}, "
            f"Structural={structural_score:.2f})"
        )

        return round(final_risk_score, 4)

    def _get_time_score(self) -> float:
        """
        Calculate time-based risk score (off-peak hours = safer)

        Peak hours (9 AM - 6 PM weekdays): Lower score (0.7)
        Off-peak hours (nights/weekends): Higher score (0.95)
        """
        now = datetime.utcnow()
        hour = now.hour
        day_of_week = now.weekday()  # 0=Monday, 6=Sunday

        # Weekend
        if day_of_week >= 5:
            return 0.95

        # Weekday night (10 PM - 6 AM)
        if hour >= 22 or hour <= 6:
            return 0.90

        # Weekday off-peak (6 AM - 9 AM, 6 PM - 10 PM)
        if (6 <= hour < 9) or (18 <= hour < 22):
            return 0.80

        # Weekday peak (9 AM - 6 PM)
        return 0.70

    async def _get_customer_feedback_weight(self) -> float:
        """
        Get current customer feedback weight (0.0 → 0.25)

        Cached for performance (weight doesn't change frequently)
        """
        if self._customer_feedback_weight is not None:
            return self._customer_feedback_weight

        if not self.db:
            return 0.0  # No database = no customer feedback

        try:
            # Query PostgreSQL calculate_feedback_weight function
            result = await self.db.execute(
                """
                SELECT calculate_feedback_weight(
                    (SELECT COALESCE(SUM(total_instance_hours), 0) FROM feedback_learning_stats),
                    (SELECT COALESCE(SUM(total_interruptions), 0) FROM feedback_learning_stats)
                )
                """
            )
            weight = result.scalar_one_or_none() or 0.0
            self._customer_feedback_weight = float(weight)

            logger.info(f"Customer feedback weight: {self._customer_feedback_weight:.2%}")
            return self._customer_feedback_weight

        except Exception as e:
            logger.warning(f"Failed to get customer feedback weight: {e}")
            return 0.0

    async def _get_learned_risk_score(
        self,
        instance_type: str,
        region: str,
        availability_zone: str
    ) -> Optional[float]:
        """
        Get learned risk score from risk_score_adjustments table

        Returns final_score if available, None otherwise
        """
        if not self.db:
            return None

        try:
            result = await self.db.execute(
                """
                SELECT final_score, confidence, data_points_count
                FROM risk_score_adjustments
                WHERE instance_type = :instance_type
                  AND region = :region
                  AND availability_zone = :availability_zone
                  AND confidence >= 0.3
                ORDER BY confidence DESC, data_points_count DESC
                LIMIT 1
                """,
                {
                    "instance_type": instance_type,
                    "region": region,
                    "availability_zone": availability_zone
                }
            )

            row = result.fetchone()
            if row:
                final_score = row[0]
                confidence = row[1]
                data_points = row[2]

                logger.debug(
                    f"Found learned risk score for {instance_type}:{availability_zone}: "
                    f"score={final_score:.4f}, confidence={confidence:.2f}, data_points={data_points}"
                )

                return float(final_score)

            return None

        except Exception as e:
            logger.warning(f"Failed to get learned risk score: {e}")
            return None

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
