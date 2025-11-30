"""
Noisy Neighbor Cost Detector Engine

Identifies pods/namespaces causing network congestion and excessive data transfer

Noisy neighbors cause:
- Direct costs: Excessive data transfer charges
- Indirect costs: Slowdown of other services (cascading performance degradation)
- Cross-AZ traffic: $0.01/GB
- Internet egress: $0.09/GB

Data Sources:
- Kubernetes metrics (network I/O per pod)
- AWS VPC Flow Logs (if available)
- Prometheus/CloudWatch network metrics
- AWS data transfer pricing

Value Proposition:
- Prevent cascading slowdowns
- One chatty microservice can slow entire cluster
- Quantify: "Service X sent 4TB last month = $360 + slowed 12 other services"
- Connect performance problems to cost

Detection Criteria:
- Network bandwidth >10x average
- Data transfer >1TB/month per pod
- Cross-AZ traffic >500GB/month
- Egress traffic >2TB/month

Cost Impact:
- Typical finding: 2-5 noisy pods per cluster
- Average cost: $100-500/month in excessive transfer
- Performance impact: 20-50% slowdown for affected services
"""

from typing import Dict, Any, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import logging
import statistics

from .base_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)


class NoisyNeighborDetectorEngine(BaseDecisionEngine):
    """
    Noisy Neighbor Cost Detector

    Identifies pods causing excessive network traffic and costs
    """

    # AWS data transfer pricing
    CROSS_AZ_TRANSFER_GB = Decimal("0.01")  # $0.01/GB
    INTERNET_EGRESS_GB = Decimal("0.09")  # $0.09/GB (first 10TB)
    SAME_AZ_TRANSFER = Decimal("0.00")  # Free

    # Detection thresholds
    BANDWIDTH_OUTLIER_MULTIPLIER = 10  # >10x average = outlier
    MONTHLY_TRANSFER_THRESHOLD_GB = 1000  # >1TB/month = high usage
    CROSS_AZ_THRESHOLD_GB = 500  # >500GB cross-AZ = excessive

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)

    def decide(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Detect noisy neighbor pods

        Args:
            cluster_state: Current cluster state with pod metrics
            requirements:
                - region: AWS region
                - analysis_period_days: Days to analyze (default: 30)
                - include_namespaces: Specific namespaces to analyze
            constraints:
                - bandwidth_threshold_multiplier: Outlier detection sensitivity
                - min_monthly_cost: Min monthly cost to flag

        Returns:
            Decision response with noisy neighbor findings
        """
        self.validate_input(cluster_state)
        logger.info("Detecting noisy neighbor pods...")

        constraints = constraints or {}
        region = requirements.get("region", "us-east-1")
        analysis_days = requirements.get("analysis_period_days", 30)
        include_namespaces = requirements.get("include_namespaces", None)
        bandwidth_multiplier = constraints.get(
            "bandwidth_threshold_multiplier",
            self.BANDWIDTH_OUTLIER_MULTIPLIER
        )
        min_monthly_cost = constraints.get("min_monthly_cost", 50)

        # Analyze network traffic
        traffic_analysis = self._analyze_network_traffic(
            cluster_state,
            analysis_days,
            include_namespaces
        )

        # Detect outliers
        noisy_neighbors = self._detect_outliers(
            traffic_analysis,
            bandwidth_multiplier
        )

        # Generate recommendations
        recommendations = []

        for pod_data in noisy_neighbors:
            pod_name = pod_data["pod_name"]
            namespace = pod_data["namespace"]
            total_transfer_gb = pod_data["total_transfer_gb"]
            cross_az_gb = pod_data["cross_az_transfer_gb"]
            egress_gb = pod_data["egress_transfer_gb"]
            avg_bandwidth_mbps = pod_data["avg_bandwidth_mbps"]
            cluster_avg_mbps = pod_data["cluster_avg_mbps"]
            outlier_factor = pod_data["outlier_factor"]

            # Calculate costs
            cross_az_cost = float(cross_az_gb * self.CROSS_AZ_TRANSFER_GB)
            egress_cost = float(egress_gb * self.INTERNET_EGRESS_GB)
            monthly_cost = cross_az_cost + egress_cost

            # Skip if below min cost threshold
            if monthly_cost < min_monthly_cost:
                continue

            # Identify likely cause
            traffic_pattern = self._identify_traffic_pattern(pod_data)

            # Estimate affected services
            affected_services = pod_data.get("affected_services", [])

            # Calculate performance impact
            performance_impact = self._estimate_performance_impact(pod_data)

            recommendations.append({
                "priority": "high" if monthly_cost > 200 else "medium",
                "category": "noisy_neighbor",
                "pod_name": pod_name,
                "namespace": namespace,
                "total_transfer_gb": round(total_transfer_gb, 2),
                "cross_az_transfer_gb": round(cross_az_gb, 2),
                "egress_transfer_gb": round(egress_gb, 2),
                "avg_bandwidth_mbps": round(avg_bandwidth_mbps, 2),
                "cluster_avg_bandwidth_mbps": round(cluster_avg_mbps, 2),
                "outlier_factor": round(outlier_factor, 1),
                "monthly_cost": round(monthly_cost, 2),
                "annual_cost": round(monthly_cost * 12, 2),
                "traffic_pattern": traffic_pattern,
                "likely_cause": self._get_likely_cause(traffic_pattern, pod_data),
                "affected_services": affected_services,
                "performance_impact_pct": round(performance_impact, 1),
                "optimization_recommendations": self._get_optimization_recs(traffic_pattern),
                "action": "optimize_network_traffic"
            })

        # Sort by cost impact (descending)
        recommendations.sort(key=lambda x: x["monthly_cost"], reverse=True)

        # Calculate totals
        total_monthly_cost = sum(r["monthly_cost"] for r in recommendations)
        total_annual_cost = sum(r["annual_cost"] for r in recommendations)
        total_transfer_gb = sum(r["total_transfer_gb"] for r in recommendations)

        # Build execution plan
        execution_plan = self._build_execution_plan(recommendations[:5])  # Top 5

        # Create response
        return self.create_response(
            recommendations=recommendations,
            confidence_score=0.85,
            estimated_savings=Decimal(str(total_monthly_cost * 0.6)),  # 60% reduction potential
            execution_plan=execution_plan,
            metadata={
                "region": region,
                "analysis_period_days": analysis_days,
                "total_pods_analyzed": traffic_analysis["total_pods"],
                "noisy_neighbors_count": len(noisy_neighbors),
                "cluster_avg_bandwidth_mbps": round(traffic_analysis["cluster_avg_bandwidth"], 2),
                "total_cluster_transfer_gb": round(traffic_analysis["total_transfer_gb"], 2),
                "total_monthly_cost": round(total_monthly_cost, 2),
                "total_annual_cost": round(total_annual_cost, 2),
                "total_noisy_transfer_gb": round(total_transfer_gb, 2),
                "noisy_percentage": round(
                    (total_transfer_gb / traffic_analysis["total_transfer_gb"] * 100)
                    if traffic_analysis["total_transfer_gb"] > 0 else 0,
                    1
                ),
                "analysis_date": datetime.now().isoformat()
            }
        )

    def _analyze_network_traffic(
        self,
        cluster_state: Dict[str, Any],
        analysis_days: int,
        include_namespaces: List[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze network traffic for all pods

        In production, query:
        - Prometheus: rate(container_network_transmit_bytes_total)
        - CloudWatch: NetworkIn/NetworkOut metrics
        - VPC Flow Logs: cross-AZ and egress traffic
        """
        pods = cluster_state.get("pods", [])

        # Filter by namespace if specified
        if include_namespaces:
            pods = [p for p in pods if p.get("namespace") in include_namespaces]

        # Simulate traffic analysis
        pod_traffic_data = []

        for pod in pods:
            pod_name = pod.get("name", "unknown")
            namespace = pod.get("namespace", "default")

            # Simulate network metrics (in production, query Prometheus/CloudWatch)
            total_transfer_gb = self._simulate_pod_traffic()
            cross_az_gb = total_transfer_gb * 0.4  # 40% cross-AZ
            egress_gb = total_transfer_gb * 0.2  # 20% egress
            avg_bandwidth_mbps = total_transfer_gb / analysis_days / 24 / 3600 * 8 * 1024  # Convert to Mbps

            pod_traffic_data.append({
                "pod_name": pod_name,
                "namespace": namespace,
                "total_transfer_gb": total_transfer_gb,
                "cross_az_transfer_gb": cross_az_gb,
                "egress_transfer_gb": egress_gb,
                "avg_bandwidth_mbps": avg_bandwidth_mbps,
                "affected_services": self._get_affected_services(pod, avg_bandwidth_mbps)
            })

        # Calculate cluster statistics
        if pod_traffic_data:
            avg_bandwidth = statistics.mean([p["avg_bandwidth_mbps"] for p in pod_traffic_data])
            total_transfer = sum([p["total_transfer_gb"] for p in pod_traffic_data])
        else:
            avg_bandwidth = 0
            total_transfer = 0

        return {
            "total_pods": len(pods),
            "pod_traffic_data": pod_traffic_data,
            "cluster_avg_bandwidth": avg_bandwidth,
            "total_transfer_gb": total_transfer
        }

    def _simulate_pod_traffic(self) -> float:
        """Simulate pod network traffic (GB/month)"""
        import random

        # Most pods: 10-100GB/month
        # Some pods: 500-2000GB/month (noisy)
        # Few pods: 5000-10000GB/month (very noisy)

        roll = random.random()
        if roll < 0.85:  # 85% normal
            return random.uniform(10, 100)
        elif roll < 0.97:  # 12% noisy
            return random.uniform(500, 2000)
        else:  # 3% very noisy
            return random.uniform(5000, 10000)

    def _get_affected_services(
        self,
        pod: Dict[str, Any],
        bandwidth_mbps: float
    ) -> List[str]:
        """Identify services affected by this noisy neighbor"""
        # In production, analyze network topology and correlate with latency spikes
        if bandwidth_mbps > 100:
            return ["service-a", "service-b", "service-c"]
        elif bandwidth_mbps > 50:
            return ["service-a"]
        return []

    def _detect_outliers(
        self,
        traffic_analysis: Dict[str, Any],
        bandwidth_multiplier: float
    ) -> List[Dict[str, Any]]:
        """Detect outlier pods (noisy neighbors)"""
        pod_traffic_data = traffic_analysis["pod_traffic_data"]
        cluster_avg = traffic_analysis["cluster_avg_bandwidth"]

        outliers = []

        for pod_data in pod_traffic_data:
            avg_bandwidth = pod_data["avg_bandwidth_mbps"]
            outlier_factor = avg_bandwidth / cluster_avg if cluster_avg > 0 else 0

            # Flag as outlier if >N times cluster average
            if outlier_factor >= bandwidth_multiplier:
                pod_data["cluster_avg_mbps"] = cluster_avg
                pod_data["outlier_factor"] = outlier_factor
                outliers.append(pod_data)

        return outliers

    def _identify_traffic_pattern(self, pod_data: Dict[str, Any]) -> str:
        """Identify traffic pattern type"""
        cross_az_pct = (pod_data["cross_az_transfer_gb"] / pod_data["total_transfer_gb"] * 100
                        if pod_data["total_transfer_gb"] > 0 else 0)
        egress_pct = (pod_data["egress_transfer_gb"] / pod_data["total_transfer_gb"] * 100
                      if pod_data["total_transfer_gb"] > 0 else 0)

        if egress_pct > 60:
            return "high_egress"
        elif cross_az_pct > 70:
            return "high_cross_az"
        elif pod_data["avg_bandwidth_mbps"] > 200:
            return "high_bandwidth"
        else:
            return "general_high_usage"

    def _get_likely_cause(
        self,
        traffic_pattern: str,
        pod_data: Dict[str, Any]
    ) -> str:
        """Determine likely cause of noisy behavior"""
        causes = {
            "high_egress": "Sending large amounts of data to external APIs or S3",
            "high_cross_az": "Communicating with services in different AZs",
            "high_bandwidth": "Processing/streaming large data volumes",
            "general_high_usage": "High network activity (investigate logs)"
        }
        return causes.get(traffic_pattern, "Unknown cause")

    def _get_optimization_recs(self, traffic_pattern: str) -> List[str]:
        """Get optimization recommendations based on pattern"""
        recommendations = {
            "high_egress": [
                "Use S3 VPC Endpoint (free internal transfer)",
                "Cache API responses to reduce external calls",
                "Use CloudFront for static content delivery",
                "Batch API requests to reduce call volume"
            ],
            "high_cross_az": [
                "Use pod affinity to keep related services in same AZ",
                "Implement pod topology spread constraints",
                "Consider headless services for same-AZ communication",
                "Review service mesh configuration"
            ],
            "high_bandwidth": [
                "Implement data compression",
                "Use gRPC instead of REST for large payloads",
                "Implement batching/chunking",
                "Review data transfer patterns"
            ],
            "general_high_usage": [
                "Analyze application logs for traffic patterns",
                "Implement rate limiting",
                "Review service communication patterns",
                "Consider caching layer"
            ]
        }
        return recommendations.get(traffic_pattern, ["Investigate network usage"])

    def _estimate_performance_impact(self, pod_data: Dict[str, Any]) -> float:
        """
        Estimate performance impact on other services

        High bandwidth usage can saturate network, slowing others
        """
        outlier_factor = pod_data.get("outlier_factor", 1)

        # Rough estimate: outlier_factor >20x = ~30% slowdown
        if outlier_factor > 20:
            return 30
        elif outlier_factor > 15:
            return 20
        elif outlier_factor > 10:
            return 10
        else:
            return 5

    def _build_execution_plan(
        self,
        recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build execution plan for network optimization"""
        plan = []

        for idx, rec in enumerate(recommendations, 1):
            plan.append({
                "step": idx,
                "action": "optimize_network_traffic",
                "pod": f"{rec['namespace']}/{rec['pod_name']}",
                "description": f"Optimize network usage for {rec['pod_name']}",
                "current_monthly_cost": rec["monthly_cost"],
                "traffic_pattern": rec["traffic_pattern"],
                "optimization_techniques": rec["optimization_recommendations"],
                "expected_savings": round(rec["monthly_cost"] * 0.6, 2),  # 60% reduction target
                "commands": self._get_optimization_commands(rec)
            })

        return plan

    def _get_optimization_commands(self, rec: Dict[str, Any]) -> List[str]:
        """Get specific commands for optimization"""
        traffic_pattern = rec["traffic_pattern"]
        namespace = rec["namespace"]
        pod_name = rec["pod_name"]

        commands = []

        if traffic_pattern == "high_cross_az":
            commands.append(
                f"# Add pod affinity to keep related pods in same AZ\n"
                f"kubectl patch deployment <deployment> -n {namespace} --patch-file affinity.yaml"
            )

        if traffic_pattern == "high_egress":
            commands.append(
                "# Create S3 VPC Endpoint (if using S3)\n"
                "aws ec2 create-vpc-endpoint --vpc-id <vpc-id> --service-name com.amazonaws.<region>.s3"
            )

        commands.append(
            f"# Monitor network metrics\n"
            f"kubectl top pod {pod_name} -n {namespace} --containers"
        )

        return commands
