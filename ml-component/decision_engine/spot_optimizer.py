"""
Spot Instance Optimizer - Decision Engine Implementation
Analyzes AWS Spot Instance market and recommends optimal instance selections
"""
from typing import Dict, Any, List
from datetime import datetime
import numpy as np
from .base_engine import BaseDecisionEngine, DecisionInput, DecisionOutput


class SpotOptimizerEngine(BaseDecisionEngine):
    """
    Spot Instance Optimizer Decision Engine
    Uses public AWS data + real-time metrics to select optimal Spot instances
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.risk_threshold = config.get('risk_threshold', 0.65)
        self.max_price_premium = config.get('max_price_premium', 1.3)
        self.diversity_requirement = config.get('diversity_requirement', 0.4)

    def validate_input(self, input_data: DecisionInput) -> bool:
        """Validate input contains required fields"""
        required_fields = ['cpu_required', 'memory_required', 'region']

        if not all(field in input_data.requirements for field in required_fields):
            return False

        return True

    def analyze(self, input_data: DecisionInput) -> DecisionOutput:
        """
        Analyze and recommend Spot instance types

        Decision Logic:
        1. Fetch compatible instance types based on CPU/memory requirements
        2. Calculate risk score for each instance type
        3. Apply diversity strategy (never >40% in single instance family)
        4. Generate execution plan
        """
        if not self.validate_input(input_data):
            raise ValueError("Invalid input data for SpotOptimizer")

        requirements = input_data.requirements
        region = requirements['region']
        cpu_needed = requirements['cpu_required']
        memory_needed = requirements['memory_required']
        node_count = requirements.get('node_count', 10)

        # Step 1: Get compatible instance types
        compatible_instances = self._get_compatible_instances(
            cpu_needed, memory_needed
        )

        # Step 2: Calculate risk scores
        scored_instances = []
        for instance_type in compatible_instances:
            risk_score = self._calculate_spot_risk_score(
                instance_type, region, datetime.now().hour
            )

            if risk_score >= self.risk_threshold:
                scored_instances.append({
                    'instance_type': instance_type,
                    'risk_score': risk_score,
                    'estimated_price': self._get_spot_price(instance_type, region),
                    'savings_vs_on_demand': self._calculate_savings(instance_type, region)
                })

        # Sort by risk score (highest first)
        scored_instances.sort(key=lambda x: x['risk_score'], reverse=True)

        # Step 3: Apply diversity strategy
        recommendations = self._apply_diversity_strategy(
            scored_instances, node_count
        )

        # Step 4: Generate execution plan
        execution_plan = self._generate_execution_plan(recommendations)

        # Step 5: Calculate total estimated savings
        total_savings = sum(r['monthly_savings'] for r in recommendations)

        # Step 6: Build risk assessment
        risk_assessment = self._build_risk_assessment(recommendations)

        return DecisionOutput(
            timestamp=datetime.now(),
            decision_type='spot_instance_selection',
            recommendations=recommendations,
            confidence_score=np.mean([r['risk_score'] for r in recommendations]),
            estimated_savings=total_savings,
            risk_assessment=risk_assessment,
            execution_plan=execution_plan,
            metadata={
                'region': region,
                'total_nodes': node_count,
                'diversity_applied': True,
                'engine_version': self.version
            }
        )

    def _get_compatible_instances(self, cpu: float, memory: float) -> List[str]:
        """
        Get instance types that meet CPU and memory requirements

        In production, this would query a database of AWS instance specs
        For now, returns common instance types
        """
        # Simplified instance database
        instance_specs = {
            'm5.large': {'vcpu': 2, 'memory_gb': 8},
            'm5.xlarge': {'vcpu': 4, 'memory_gb': 16},
            'm5.2xlarge': {'vcpu': 8, 'memory_gb': 32},
            'm5a.large': {'vcpu': 2, 'memory_gb': 8},
            'm5a.xlarge': {'vcpu': 4, 'memory_gb': 16},
            'c5.large': {'vcpu': 2, 'memory_gb': 4},
            'c5.xlarge': {'vcpu': 4, 'memory_gb': 8},
            'c5.2xlarge': {'vcpu': 8, 'memory_gb': 16},
            'r5.large': {'vcpu': 2, 'memory_gb': 16},
            'r5.xlarge': {'vcpu': 4, 'memory_gb': 32},
        }

        compatible = []
        for instance_type, specs in instance_specs.items():
            if specs['vcpu'] >= cpu and specs['memory_gb'] >= memory:
                compatible.append(instance_type)

        return compatible

    def _calculate_spot_risk_score(
        self, instance_type: str, region: str, hour_of_day: int
    ) -> float:
        """
        Calculate spot interruption risk score (0.0 to 1.0)

        Formula based on CloudOptim spec:
        - 60% weight: Public interruption rate
        - 25% weight: Price volatility
        - 10% weight: Spot vs On-Demand gap
        - 5% weight: Time of day
        """
        # Factor 1: Public Interruption Rate (from Spot Advisor)
        public_rate_score = self._get_public_interruption_score(instance_type)

        # Factor 2: Price Volatility
        volatility_score = self._calculate_price_volatility(instance_type, region)

        # Factor 3: Spot vs On-Demand Gap
        gap_score = self._calculate_price_gap_score(instance_type, region)

        # Factor 4: Time of Day
        time_score = self._calculate_time_score(hour_of_day)

        # Weighted composite
        final_score = (
            0.60 * public_rate_score +
            0.25 * volatility_score +
            0.10 * gap_score +
            0.05 * time_score
        )

        return final_score

    def _get_public_interruption_score(self, instance_type: str) -> float:
        """
        Get public interruption rate score
        In production, this would fetch from Redis cache of Spot Advisor data
        """
        # Simulate Spot Advisor risk buckets
        # 0=<5%, 1=5-10%, 2=10-15%, 3=15-20%, 4=>20%
        risk_bucket_map = {
            'm5.large': 0,      # <5% interruption rate
            'm5.xlarge': 1,     # 5-10%
            'm5.2xlarge': 2,    # 10-15%
            'm5a.large': 0,     # <5%
            'm5a.xlarge': 0,    # <5%
            'c5.large': 0,      # <5%
            'c5.xlarge': 1,     # 5-10%
            'c5.2xlarge': 1,    # 5-10%
            'r5.large': 2,      # 10-15%
            'r5.xlarge': 2,     # 10-15%
        }

        bucket_scores = {0: 1.0, 1: 0.75, 2: 0.5, 3: 0.25, 4: 0.0}
        risk_bucket = risk_bucket_map.get(instance_type, 2)

        return bucket_scores[risk_bucket]

    def _calculate_price_volatility(self, instance_type: str, region: str) -> float:
        """Calculate price volatility score"""
        # In production: fetch 24h price history from AWS
        # For now: simulate with random volatility
        simulated_volatility = np.random.uniform(0.05, 0.15)
        volatility_score = max(0, 1.0 - (simulated_volatility / 0.20))
        return volatility_score

    def _calculate_price_gap_score(self, instance_type: str, region: str) -> float:
        """Calculate Spot vs On-Demand price gap score"""
        # In production: query real-time prices
        # Larger gap = better score (more capacity available)
        simulated_discount = np.random.uniform(0.50, 0.70)  # 50-70% discount
        gap_score = min(1.0, simulated_discount / 0.30)
        return gap_score

    def _calculate_time_score(self, hour: int) -> float:
        """Time-of-day risk scoring"""
        # Peak hours: 9-11 AM EST = higher demand
        if 9 <= hour <= 11:
            return 0.7
        else:
            return 1.0

    def _get_spot_price(self, instance_type: str, region: str) -> float:
        """Get current spot price"""
        # Simulated prices (in production: query AWS API)
        base_prices = {
            'm5.large': 0.032,
            'm5.xlarge': 0.064,
            'm5.2xlarge': 0.128,
            'm5a.large': 0.029,
            'm5a.xlarge': 0.058,
            'c5.large': 0.035,
            'c5.xlarge': 0.070,
            'c5.2xlarge': 0.140,
            'r5.large': 0.045,
            'r5.xlarge': 0.090,
        }
        return base_prices.get(instance_type, 0.05)

    def _calculate_savings(self, instance_type: str, region: str) -> float:
        """Calculate savings vs On-Demand"""
        spot_price = self._get_spot_price(instance_type, region)
        on_demand_price = spot_price / 0.65  # Assume 65% discount
        savings = (on_demand_price - spot_price) * 730  # Monthly hours
        return savings

    def _apply_diversity_strategy(
        self, scored_instances: List[Dict], node_count: int
    ) -> List[Dict]:
        """
        Apply diversity strategy: Never >40% of nodes in single instance family
        """
        max_per_family = int(node_count * self.diversity_requirement)

        recommendations = []
        family_counts = {}
        remaining_nodes = node_count

        for instance in scored_instances:
            if remaining_nodes <= 0:
                break

            instance_type = instance['instance_type']
            family = instance_type.split('.')[0]  # e.g., 'm5' from 'm5.large'

            current_count = family_counts.get(family, 0)

            if current_count < max_per_family:
                # Allocate nodes to this instance type
                nodes_to_allocate = min(
                    max_per_family - current_count,
                    remaining_nodes
                )

                recommendations.append({
                    'instance_type': instance_type,
                    'node_count': nodes_to_allocate,
                    'risk_score': instance['risk_score'],
                    'hourly_price': instance['estimated_price'],
                    'monthly_savings': instance['savings_vs_on_demand'] * nodes_to_allocate
                })

                family_counts[family] = current_count + nodes_to_allocate
                remaining_nodes -= nodes_to_allocate

        return recommendations

    def _generate_execution_plan(self, recommendations: List[Dict]) -> List[Dict]:
        """Generate step-by-step execution plan"""
        plan = []

        for idx, rec in enumerate(recommendations):
            plan.append({
                'step': idx + 1,
                'action': 'launch_spot_instances',
                'instance_type': rec['instance_type'],
                'count': rec['node_count'],
                'max_price': rec['hourly_price'] * 1.1,  # 10% buffer
                'allocation_strategy': 'price-capacity-optimized',
                'interruption_behavior': 'terminate',
                'tags': {
                    'ManagedBy': 'CloudOptim',
                    'OptimizationType': 'SpotArbitrage'
                }
            })

        return plan

    def _build_risk_assessment(self, recommendations: List[Dict]) -> Dict[str, Any]:
        """Build comprehensive risk assessment"""
        risk_scores = [r['risk_score'] for r in recommendations]

        return {
            'overall_risk_level': 'LOW' if np.mean(risk_scores) > 0.75 else 'MEDIUM',
            'average_risk_score': np.mean(risk_scores),
            'min_risk_score': np.min(risk_scores),
            'max_risk_score': np.max(risk_scores),
            'diversity_applied': True,
            'fallback_strategy': 'on_demand_replacement',
            'estimated_availability': '99.5%'
        }
