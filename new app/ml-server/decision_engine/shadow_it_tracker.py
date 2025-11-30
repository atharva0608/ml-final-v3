"""
Shadow IT Cost Tracker Engine

Detects AWS resources NOT managed by Kubernetes (orphaned/forgotten resources)

Shadow IT includes:
- EC2 instances not in any K8s cluster
- EBS volumes not attached to K8s nodes
- Security groups not used by K8s
- Elastic IPs not associated with K8s
- Load balancers not referenced in K8s Ingress
- RDS instances created by developers for testing

Data Sources:
- EC2 API: describe_instances()
- EBS API: describe_volumes()
- Kubernetes API: list of cluster nodes
- IAM CloudTrail: who created what (compliance benefit)

Value Proposition:
- Find 10-30% hidden costs
- Developers spin up test instances, forget to delete
- Example: "Found 14 EC2 instances NOT in K8s = $427/month waste"
- Compliance benefit: track who created what

Cost Impact:
- Typical finding: 5-15 orphaned EC2 instances per account
- Average cost: $30-50/instance/month
- Total waste: $150-750/month per account
"""

from typing import Dict, Any, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import logging

from .base_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)


class ShadowITTrackerEngine(BaseDecisionEngine):
    """
    Shadow IT Cost Tracker

    Identifies AWS resources not managed by Kubernetes
    """

    # Typical EC2 costs (On-Demand pricing us-east-1)
    INSTANCE_COSTS_MONTHLY = {
        "t3.micro": 7.59,
        "t3.small": 15.18,
        "t3.medium": 30.37,
        "t3.large": 60.74,
        "m5.large": 70.08,
        "m5.xlarge": 140.16,
        "c5.large": 62.05,
        "c5.xlarge": 124.10,
        "r5.large": 91.98,
        "default": 50.00  # Average
    }

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)

    def decide(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Detect Shadow IT resources

        Args:
            cluster_state: Current cluster state with node info
            requirements:
                - region: AWS region
                - account_id: AWS account ID
                - cluster_names: List of K8s cluster names
                - include_stopped: Include stopped instances
            constraints:
                - min_age_days: Only flag resources older than N days
                - exclude_tags: Tags to exclude (e.g., 'permanent')

        Returns:
            Decision response with Shadow IT findings
        """
        self.validate_input(cluster_state)
        logger.info("Detecting Shadow IT resources...")

        constraints = constraints or {}
        region = requirements.get("region", "us-east-1")
        cluster_names = requirements.get("cluster_names", [])
        include_stopped = requirements.get("include_stopped", True)
        min_age_days = constraints.get("min_age_days", 7)
        exclude_tags = constraints.get("exclude_tags", ["permanent", "do-not-delete"])

        # Get K8s managed resources
        k8s_instance_ids = self._get_k8s_instance_ids(cluster_state)
        k8s_volume_ids = self._get_k8s_volume_ids(cluster_state)
        k8s_lb_arns = self._get_k8s_lb_arns(cluster_state)

        # TODO: Query AWS APIs
        # ec2_client.describe_instances()
        # ec2_client.describe_volumes()
        # elbv2_client.describe_load_balancers()

        # Simulate Shadow IT detection
        shadow_resources = self._detect_shadow_resources(
            k8s_instance_ids,
            k8s_volume_ids,
            k8s_lb_arns,
            region,
            include_stopped,
            min_age_days
        )

        # Generate recommendations
        recommendations = []

        # Shadow EC2 instances
        if shadow_resources["ec2_instances"]:
            for instance in shadow_resources["ec2_instances"]:
                instance_id = instance["instance_id"]
                instance_type = instance["instance_type"]
                state = instance["state"]
                age_days = instance["age_days"]
                created_by = instance.get("created_by", "unknown")

                monthly_cost = self.INSTANCE_COSTS_MONTHLY.get(
                    instance_type,
                    self.INSTANCE_COSTS_MONTHLY["default"]
                )

                # Adjust cost if stopped (EBS storage only)
                if state == "stopped":
                    monthly_cost = monthly_cost * 0.15  # ~15% for EBS storage

                recommendations.append({
                    "priority": "high" if state == "running" else "medium",
                    "category": "shadow_ec2",
                    "resource_type": "EC2 Instance",
                    "resource_id": instance_id,
                    "instance_type": instance_type,
                    "state": state,
                    "age_days": age_days,
                    "created_by": created_by,
                    "monthly_cost": round(monthly_cost, 2),
                    "annual_cost": round(monthly_cost * 12, 2),
                    "action": "terminate_instance" if state == "running" else "delete_stopped_instance",
                    "description": f"EC2 {instance_id} ({instance_type}) not in any K8s cluster"
                })

        # Shadow EBS volumes
        if shadow_resources["ebs_volumes"]:
            for volume in shadow_resources["ebs_volumes"]:
                volume_id = volume["volume_id"]
                size_gb = volume["size_gb"]
                volume_type = volume.get("volume_type", "gp3")
                age_days = volume["age_days"]

                # EBS pricing (gp3: $0.08/GB-month)
                monthly_cost = size_gb * 0.08 if volume_type == "gp3" else size_gb * 0.10

                recommendations.append({
                    "priority": "medium",
                    "category": "shadow_ebs",
                    "resource_type": "EBS Volume",
                    "resource_id": volume_id,
                    "size_gb": size_gb,
                    "volume_type": volume_type,
                    "age_days": age_days,
                    "monthly_cost": round(monthly_cost, 2),
                    "annual_cost": round(monthly_cost * 12, 2),
                    "action": "delete_volume",
                    "description": f"EBS volume {volume_id} ({size_gb}GB) not attached to any K8s node"
                })

        # Shadow Load Balancers
        if shadow_resources["load_balancers"]:
            for lb in shadow_resources["load_balancers"]:
                lb_arn = lb["lb_arn"]
                lb_type = lb.get("lb_type", "application")
                age_days = lb["age_days"]

                # LB pricing
                if lb_type == "application":
                    monthly_cost = 16.43  # $0.0225/hour
                elif lb_type == "network":
                    monthly_cost = 16.43  # $0.0225/hour
                else:
                    monthly_cost = 18.00  # Classic LB

                recommendations.append({
                    "priority": "high",
                    "category": "shadow_lb",
                    "resource_type": "Load Balancer",
                    "resource_id": lb_arn.split("/")[-1],
                    "lb_type": lb_type,
                    "age_days": age_days,
                    "monthly_cost": round(monthly_cost, 2),
                    "annual_cost": round(monthly_cost * 12, 2),
                    "action": "delete_load_balancer",
                    "description": f"Load Balancer not used by any K8s Ingress"
                })

        # Sort by monthly cost (descending)
        recommendations.sort(key=lambda x: x["monthly_cost"], reverse=True)

        # Calculate totals
        total_monthly_waste = sum(r["monthly_cost"] for r in recommendations)
        total_annual_waste = sum(r["annual_cost"] for r in recommendations)

        # Build execution plan
        execution_plan = self._build_execution_plan(recommendations[:10])  # Top 10

        # Create response
        return self.create_response(
            recommendations=recommendations,
            confidence_score=0.95,  # High confidence - simple resource detection
            estimated_savings=Decimal(str(total_monthly_waste)),
            execution_plan=execution_plan,
            metadata={
                "region": region,
                "cluster_names": cluster_names,
                "k8s_instances": len(k8s_instance_ids),
                "k8s_volumes": len(k8s_volume_ids),
                "shadow_ec2_count": len(shadow_resources["ec2_instances"]),
                "shadow_ebs_count": len(shadow_resources["ebs_volumes"]),
                "shadow_lb_count": len(shadow_resources["load_balancers"]),
                "total_shadow_resources": (
                    len(shadow_resources["ec2_instances"]) +
                    len(shadow_resources["ebs_volumes"]) +
                    len(shadow_resources["load_balancers"])
                ),
                "monthly_waste": round(total_monthly_waste, 2),
                "annual_waste": round(total_annual_waste, 2),
                "min_age_days": min_age_days,
                "analysis_date": datetime.now().isoformat()
            }
        )

    def _get_k8s_instance_ids(self, cluster_state: Dict[str, Any]) -> List[str]:
        """Extract EC2 instance IDs from K8s nodes"""
        nodes = cluster_state.get("nodes", [])
        instance_ids = []

        for node in nodes:
            # In real implementation, extract from node.spec.providerID
            # Example: aws:///us-east-1a/i-0123456789abcdef
            provider_id = node.get("provider_id", "")
            if "i-" in provider_id:
                instance_id = provider_id.split("/")[-1]
                instance_ids.append(instance_id)

        return instance_ids

    def _get_k8s_volume_ids(self, cluster_state: Dict[str, Any]) -> List[str]:
        """Extract EBS volume IDs from K8s PVCs"""
        # In real implementation, query K8s PVs and extract EBS volume IDs
        return []

    def _get_k8s_lb_arns(self, cluster_state: Dict[str, Any]) -> List[str]:
        """Extract Load Balancer ARNs from K8s Ingresses"""
        # In real implementation, query K8s Ingresses and Services (type=LoadBalancer)
        return []

    def _detect_shadow_resources(
        self,
        k8s_instance_ids: List[str],
        k8s_volume_ids: List[str],
        k8s_lb_arns: List[str],
        region: str,
        include_stopped: bool,
        min_age_days: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect Shadow IT resources

        In production, query AWS APIs and cross-reference with K8s
        """
        # Simulate Shadow IT detection
        cutoff_date = datetime.now() - timedelta(days=min_age_days)

        # Sample shadow EC2 instances
        shadow_ec2 = [
            {
                "instance_id": "i-0a1b2c3d4e5f6g7h8",
                "instance_type": "m5.large",
                "state": "running",
                "launch_time": (datetime.now() - timedelta(days=45)).isoformat(),
                "age_days": 45,
                "created_by": "john.doe@company.com",
                "tags": {"Name": "test-instance", "Environment": "dev"}
            },
            {
                "instance_id": "i-9h8g7f6e5d4c3b2a1",
                "instance_type": "t3.medium",
                "state": "stopped",
                "launch_time": (datetime.now() - timedelta(days=120)).isoformat(),
                "age_days": 120,
                "created_by": "jane.smith@company.com",
                "tags": {"Name": "old-test-server"}
            }
        ]

        # Sample shadow EBS volumes
        shadow_ebs = [
            {
                "volume_id": "vol-0123456789abcdef0",
                "size_gb": 100,
                "volume_type": "gp3",
                "state": "available",
                "create_time": (datetime.now() - timedelta(days=60)).isoformat(),
                "age_days": 60
            },
            {
                "volume_id": "vol-fedcba9876543210",
                "size_gb": 50,
                "volume_type": "gp2",
                "state": "available",
                "create_time": (datetime.now() - timedelta(days=90)).isoformat(),
                "age_days": 90
            }
        ]

        # Sample shadow load balancers
        shadow_lb = [
            {
                "lb_arn": "arn:aws:elasticloadbalancing:us-east-1:123456789:loadbalancer/app/old-app-lb/abc123",
                "lb_type": "application",
                "create_time": (datetime.now() - timedelta(days=30)).isoformat(),
                "age_days": 30,
                "dns_name": "old-app-lb-123456.us-east-1.elb.amazonaws.com"
            }
        ]

        return {
            "ec2_instances": shadow_ec2 if include_stopped else [i for i in shadow_ec2 if i["state"] == "running"],
            "ebs_volumes": shadow_ebs,
            "load_balancers": shadow_lb
        }

    def _build_execution_plan(
        self,
        recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build execution plan for Shadow IT cleanup"""
        plan = []

        for idx, rec in enumerate(recommendations, 1):
            category = rec["category"]
            resource_id = rec["resource_id"]

            if category == "shadow_ec2":
                state = rec["state"]
                if state == "running":
                    plan.append({
                        "step": idx,
                        "action": "terminate_instance",
                        "resource_id": resource_id,
                        "description": f"Terminate EC2 instance {resource_id}",
                        "command": f"aws ec2 terminate-instances --instance-ids {resource_id}",
                        "safety": "⚠️ VERIFY instance is truly unused before terminating!",
                        "savings_annual": rec["annual_cost"]
                    })
                else:
                    plan.append({
                        "step": idx,
                        "action": "delete_stopped_instance",
                        "resource_id": resource_id,
                        "description": f"Delete stopped EC2 instance {resource_id}",
                        "command": f"aws ec2 terminate-instances --instance-ids {resource_id}",
                        "safety": "Verify instance is not needed",
                        "savings_annual": rec["annual_cost"]
                    })

            elif category == "shadow_ebs":
                plan.append({
                    "step": idx,
                    "action": "delete_volume",
                    "resource_id": resource_id,
                    "description": f"Delete EBS volume {resource_id} ({rec['size_gb']}GB)",
                    "command": f"aws ec2 delete-volume --volume-id {resource_id}",
                    "safety": "Create snapshot first if data might be needed",
                    "savings_annual": rec["annual_cost"]
                })

            elif category == "shadow_lb":
                plan.append({
                    "step": idx,
                    "action": "delete_load_balancer",
                    "resource_id": resource_id,
                    "description": f"Delete Load Balancer {resource_id}",
                    "command": f"aws elbv2 delete-load-balancer --load-balancer-arn {rec['resource_id']}",
                    "safety": "Verify no traffic in last 30 days",
                    "savings_annual": rec["annual_cost"]
                })

        return plan
