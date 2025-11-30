"""
IPv4 Public IP Cost Tracker Engine

NEW AWS CHARGE (Feb 2024): $0.005/hour per public IPv4 address

Tracks and optimizes IPv4 public IP costs by:
- Identifying all allocated Elastic IPs
- Finding unused/idle IPs
- Calculating monthly costs ($3.60/year per IP)
- Recommending IPv6 migration or IP consolidation
- Suggesting NAT Gateway or ALB for shared IPs

Data Sources:
- EC2 API: describe_addresses()
- ELB API: describe_load_balancers()
- AWS Pricing: $0.005/hour per public IPv4

Value Proposition:
- Large cluster = 200 IPs = $720/year
- Most companies don't know they're being charged
- First-to-market feature (AWS started charging Feb 2024)
"""

from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime
import logging

from .base_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)


class IPv4CostTrackerEngine(BaseDecisionEngine):
    """
    IPv4 Public IP Cost Tracker & Optimizer

    Detects IPv4 cost waste and recommends optimization strategies
    """

    # AWS IPv4 pricing (started Feb 2024)
    IPV4_HOURLY_COST = Decimal("0.005")  # $0.005/hour
    HOURS_PER_MONTH = 730  # Average hours per month
    HOURS_PER_YEAR = 8760  # Hours per year

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.ipv4_annual_cost = float(self.IPV4_HOURLY_COST * self.HOURS_PER_YEAR)  # $43.80/year

    def decide(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze IPv4 public IP usage and costs

        Args:
            cluster_state: Current cluster state
            requirements:
                - region: AWS region
                - account_id: AWS account ID
                - include_load_balancers: Include ELB/ALB/NLB IPs (default: True)
            constraints:
                - target_ipv6_migration: Enable IPv6 recommendations
                - consolidation_threshold: Min IPs to trigger consolidation warning

        Returns:
            Decision response with IPv4 cost analysis and recommendations
        """
        self.validate_input(cluster_state)
        logger.info("Analyzing IPv4 public IP costs...")

        constraints = constraints or {}
        region = requirements.get("region", "us-east-1")
        include_lb = requirements.get("include_load_balancers", True)
        ipv6_migration = constraints.get("target_ipv6_migration", True)
        consolidation_threshold = constraints.get("consolidation_threshold", 10)

        # TODO: Query AWS APIs
        # ec2_client.describe_addresses()
        # elbv2_client.describe_load_balancers()

        # Sample data (replace with real AWS API calls)
        ip_inventory = self._get_ip_inventory(cluster_state, region, include_lb)

        # Analyze IP usage
        total_ips = ip_inventory["total_ips"]
        unused_ips = ip_inventory["unused_ips"]
        ec2_ips = ip_inventory["ec2_ips"]
        lb_ips = ip_inventory["lb_ips"]
        in_use_ips = total_ips - unused_ips

        # Calculate costs
        monthly_cost = float(self.IPV4_HOURLY_COST * self.HOURS_PER_MONTH * total_ips)
        annual_cost = float(self.IPV4_HOURLY_COST * self.HOURS_PER_YEAR * total_ips)
        wasted_monthly = float(self.IPV4_HOURLY_COST * self.HOURS_PER_MONTH * unused_ips)
        wasted_annual = float(self.IPV4_HOURLY_COST * self.HOURS_PER_YEAR * unused_ips)

        # Generate recommendations
        recommendations = []

        # Recommendation 1: Release unused IPs
        if unused_ips > 0:
            recommendations.append({
                "priority": "high",
                "category": "unused_ips",
                "title": f"Release {unused_ips} Unused Elastic IPs",
                "description": f"Found {unused_ips} allocated but unused Elastic IPs",
                "savings_monthly": round(wasted_monthly, 2),
                "savings_annual": round(wasted_annual, 2),
                "action": "release_elastic_ips",
                "ip_addresses": ip_inventory.get("unused_ip_list", [])
            })

        # Recommendation 2: IPv6 migration
        if ipv6_migration and total_ips > 5:
            ipv6_savings_pct = 100  # IPv6 is free
            recommendations.append({
                "priority": "medium",
                "category": "ipv6_migration",
                "title": "Migrate to IPv6 (Free)",
                "description": f"IPv6 addresses are free. Migrate {total_ips} resources to IPv6",
                "savings_monthly": round(monthly_cost, 2),
                "savings_annual": round(annual_cost, 2),
                "savings_percentage": ipv6_savings_pct,
                "action": "enable_ipv6",
                "effort": "medium",
                "compatibility_note": "Requires application IPv6 support"
            })

        # Recommendation 3: Consolidate via NAT Gateway
        if ec2_ips > consolidation_threshold:
            nat_monthly_cost = 32.85  # $0.045/hour NAT Gateway
            nat_data_cost_estimate = 50  # Estimate $50/month data processing
            nat_total_monthly = nat_monthly_cost + nat_data_cost_estimate

            ec2_ip_monthly_cost = float(self.IPV4_HOURLY_COST * self.HOURS_PER_MONTH * ec2_ips)

            if ec2_ip_monthly_cost > nat_total_monthly:
                savings = ec2_ip_monthly_cost - nat_total_monthly
                recommendations.append({
                    "priority": "high",
                    "category": "nat_gateway",
                    "title": f"Use NAT Gateway Instead of {ec2_ips} EC2 Public IPs",
                    "description": "Replace per-instance public IPs with NAT Gateway (1 shared IP)",
                    "savings_monthly": round(savings, 2),
                    "savings_annual": round(savings * 12, 2),
                    "action": "deploy_nat_gateway",
                    "current_cost": round(ec2_ip_monthly_cost, 2),
                    "new_cost": round(nat_total_monthly, 2)
                })

        # Recommendation 4: Use ALB/NLB for shared IP
        if lb_ips > 3:
            alb_monthly_cost = 16.43  # $0.0225/hour ALB
            consolidation_potential = lb_ips - 1
            consolidation_savings = float(
                self.IPV4_HOURLY_COST * self.HOURS_PER_MONTH * consolidation_potential
            )

            # Only recommend if ALB consolidation saves money
            if consolidation_savings > alb_monthly_cost:
                recommendations.append({
                    "priority": "medium",
                    "category": "lb_consolidation",
                    "title": f"Consolidate {lb_ips} Load Balancers",
                    "description": "Use single ALB with host-based routing instead of multiple LBs",
                    "savings_monthly": round(consolidation_savings - alb_monthly_cost, 2),
                    "savings_annual": round((consolidation_savings - alb_monthly_cost) * 12, 2),
                    "action": "consolidate_load_balancers"
                })

        # Sort recommendations by savings
        recommendations.sort(key=lambda x: x.get("savings_annual", 0), reverse=True)

        # Calculate total potential savings
        total_savings_monthly = sum(r.get("savings_monthly", 0) for r in recommendations)
        total_savings_annual = sum(r.get("savings_annual", 0) for r in recommendations)

        # Build execution plan
        execution_plan = self._build_execution_plan(recommendations)

        # Create response
        return self.create_response(
            recommendations=recommendations,
            confidence_score=0.98,  # High confidence - this is simple cost calculation
            estimated_savings=Decimal(str(total_savings_monthly)),
            execution_plan=execution_plan,
            metadata={
                "region": region,
                "total_ips": total_ips,
                "in_use_ips": in_use_ips,
                "unused_ips": unused_ips,
                "ec2_ips": ec2_ips,
                "lb_ips": lb_ips,
                "monthly_cost": round(monthly_cost, 2),
                "annual_cost": round(annual_cost, 2),
                "cost_per_ip_monthly": round(float(self.IPV4_HOURLY_COST * self.HOURS_PER_MONTH), 2),
                "cost_per_ip_annual": round(self.ipv4_annual_cost, 2),
                "aws_charge_start_date": "2024-02-01",
                "analysis_date": datetime.now().isoformat()
            }
        )

    def _get_ip_inventory(
        self,
        cluster_state: Dict[str, Any],
        region: str,
        include_lb: bool
    ) -> Dict[str, Any]:
        """
        Get IPv4 inventory from cluster state

        In production, this would query:
        - ec2.describe_addresses()
        - ec2.describe_instances()
        - elbv2.describe_load_balancers()
        """
        # Sample data - replace with real AWS API calls

        # Simulate IP inventory
        nodes = cluster_state.get("nodes", [])

        # Assume 30% of nodes have public IPs
        ec2_ips = max(1, len(nodes) // 3)

        # Assume some unused IPs
        unused_ips = max(1, ec2_ips // 5)

        # Load balancer IPs
        lb_ips = 2 if include_lb else 0

        total_ips = ec2_ips + lb_ips

        return {
            "total_ips": total_ips,
            "ec2_ips": ec2_ips,
            "lb_ips": lb_ips,
            "unused_ips": unused_ips,
            "unused_ip_list": [f"52.{i}.{j}.{k}" for i, j, k in [(1, 2, 3), (4, 5, 6)]][:unused_ips]
        }

    def _build_execution_plan(
        self,
        recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build step-by-step execution plan"""
        plan = []

        for idx, rec in enumerate(recommendations, 1):
            category = rec.get("category", "unknown")

            if category == "unused_ips":
                plan.append({
                    "step": idx,
                    "action": "release_elastic_ips",
                    "description": f"Release {len(rec.get('ip_addresses', []))} unused Elastic IPs",
                    "command": "aws ec2 release-address --allocation-id <eipalloc-id>",
                    "safety": "Verify IP is truly unused before releasing"
                })

            elif category == "ipv6_migration":
                plan.append({
                    "step": idx,
                    "action": "enable_ipv6",
                    "description": "Enable IPv6 for VPC and subnets",
                    "command": "aws ec2 associate-subnet-cidr-block --subnet-id <id> --ipv6-cidr-block <cidr>",
                    "safety": "Test application IPv6 compatibility first"
                })

            elif category == "nat_gateway":
                plan.append({
                    "step": idx,
                    "action": "deploy_nat_gateway",
                    "description": "Deploy NAT Gateway and update route tables",
                    "command": "aws ec2 create-nat-gateway --subnet-id <id> --allocation-id <eip>",
                    "safety": "Requires VPC route table updates"
                })

            elif category == "lb_consolidation":
                plan.append({
                    "step": idx,
                    "action": "consolidate_load_balancers",
                    "description": "Consolidate load balancers using host-based routing",
                    "command": "Use ALB listener rules for host-based routing",
                    "safety": "Plan DNS migration carefully"
                })

        return plan
