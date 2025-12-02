"""
Container Image Bloat Tax Calculator Engine

Analyzes Docker/container image sizes and calculates wasted costs from:
- ECR storage costs
- Data transfer costs (cross-AZ, cross-region pulls)
- Slower pod startup times (affects auto-scaling)

Data Sources:
- ECR API: describe_images(), list_images()
- Docker Registry API v2
- Kubernetes pod specs (image sizes)
- AWS data transfer pricing

Value Proposition:
- 10-40% savings on data transfer + storage
- Faster pod startup = better auto-scaling responsiveness
- Most teams ship 2GB images when 200MB would work
- Viral factor: "Your image was 92% bloat!"

Cost Factors:
- ECR Storage: $0.10/GB-month
- Cross-AZ Transfer: $0.01/GB
- Internet Transfer: $0.09/GB
- Typical pull frequency: 50-200 pulls/day for active services
"""

from typing import Dict, Any, List, Tuple
from decimal import Decimal
from datetime import datetime
import logging
import re

from .base_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)


class ImageBloatAnalyzerEngine(BaseDecisionEngine):
    """
    Container Image Bloat Tax Calculator

    Identifies oversized container images and calculates cost waste
    """

    # AWS ECR and data transfer pricing
    ECR_STORAGE_GB_MONTH = Decimal("0.10")  # $0.10/GB-month
    CROSS_AZ_TRANSFER_GB = Decimal("0.01")  # $0.01/GB
    INTERNET_TRANSFER_GB = Decimal("0.09")  # $0.09/GB (first 10TB)

    # Base image sizes (MB) - known good minimal images
    MINIMAL_IMAGE_SIZES = {
        "alpine": 5,
        "busybox": 1,
        "scratch": 0,
        "distroless": 20,
        "python:3.11-slim": 125,
        "node:20-alpine": 110,
        "golang:1.21-alpine": 310,
        "nginx:alpine": 25
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
        Analyze container image bloat and calculate costs

        Args:
            cluster_state: Current cluster state with pod info
            requirements:
                - registry_type: 'ecr' | 'dockerhub' | 'gcr'
                - region: AWS region (for ECR)
                - include_recommendations: Include optimization tips
            constraints:
                - bloat_threshold_mb: Min size to flag as bloated (default: 500)
                - target_size_reduction_pct: Target reduction % (default: 50)

        Returns:
            Decision response with bloat analysis and cost savings
        """
        self.validate_input(cluster_state)
        logger.info("Analyzing container image bloat...")

        constraints = constraints or {}
        registry_type = requirements.get("registry_type", "ecr")
        region = requirements.get("region", "us-east-1")
        include_recs = requirements.get("include_recommendations", True)
        bloat_threshold_mb = constraints.get("bloat_threshold_mb", 500)
        target_reduction_pct = constraints.get("target_size_reduction_pct", 50)

        # Analyze images
        image_analysis = self._analyze_images(cluster_state, bloat_threshold_mb)

        # Calculate costs
        cost_analysis = self._calculate_costs(image_analysis, region)

        # Generate recommendations
        recommendations = []

        for image_data in image_analysis["bloated_images"]:
            image_name = image_data["image"]
            current_size_mb = image_data["size_mb"]
            potential_size_mb = current_size_mb * (1 - target_reduction_pct / 100)
            size_reduction_mb = current_size_mb - potential_size_mb

            # Calculate savings
            storage_savings = self._calc_storage_savings(size_reduction_mb)
            transfer_savings = self._calc_transfer_savings(
                size_reduction_mb,
                image_data.get("pull_frequency", 10)
            )

            monthly_savings = storage_savings + transfer_savings
            annual_savings = monthly_savings * 12

            # Determine bloat reason
            bloat_reasons = self._identify_bloat_reasons(image_data)

            recommendations.append({
                "priority": "high" if current_size_mb > 1000 else "medium",
                "category": "image_optimization",
                "image": image_name,
                "current_size_mb": round(current_size_mb, 1),
                "potential_size_mb": round(potential_size_mb, 1),
                "size_reduction_mb": round(size_reduction_mb, 1),
                "size_reduction_pct": target_reduction_pct,
                "bloat_percentage": round((size_reduction_mb / current_size_mb) * 100, 1),
                "bloat_reasons": bloat_reasons,
                "savings_monthly": round(float(monthly_savings), 2),
                "savings_annual": round(float(annual_savings), 2),
                "startup_time_improvement_sec": self._estimate_startup_improvement(size_reduction_mb),
                "optimization_techniques": self._get_optimization_techniques(bloat_reasons),
                "action": "optimize_image"
            })

        # Sort by savings potential
        recommendations.sort(key=lambda x: x["savings_annual"], reverse=True)

        # Calculate total savings
        total_monthly_savings = sum(r["savings_monthly"] for r in recommendations)
        total_annual_savings = sum(r["savings_annual"] for r in recommendations)

        # Build execution plan
        execution_plan = self._build_execution_plan(recommendations[:5])  # Top 5

        # Create response
        return self.create_response(
            recommendations=recommendations,
            confidence_score=0.90,
            estimated_savings=Decimal(str(total_monthly_savings)),
            execution_plan=execution_plan,
            metadata={
                "registry_type": registry_type,
                "region": region,
                "total_images": image_analysis["total_images"],
                "bloated_images": len(image_analysis["bloated_images"]),
                "avg_image_size_mb": round(image_analysis["avg_size_mb"], 1),
                "total_storage_gb": round(image_analysis["total_size_gb"], 2),
                "monthly_ecr_storage_cost": round(float(cost_analysis["storage_cost_monthly"]), 2),
                "monthly_transfer_cost": round(float(cost_analysis["transfer_cost_monthly"]), 2),
                "total_monthly_cost": round(float(cost_analysis["total_monthly_cost"]), 2),
                "potential_monthly_savings": round(total_monthly_savings, 2),
                "potential_annual_savings": round(total_annual_savings, 2),
                "analysis_date": datetime.now().isoformat()
            }
        )

    def _analyze_images(
        self,
        cluster_state: Dict[str, Any],
        bloat_threshold_mb: int
    ) -> Dict[str, Any]:
        """
        Analyze container images in cluster

        In production, query:
        - ECR: ecr.describe_images()
        - Kubernetes: Get image sizes from pod specs
        """
        pods = cluster_state.get("pods", [])

        # Extract unique images
        image_data = {}

        for pod in pods:
            containers = pod.get("spec", {}).get("containers", [])
            for container in containers:
                image = container.get("image", "")

                if image not in image_data:
                    # Simulate image size (in production, query ECR)
                    size_mb = self._estimate_image_size(image)

                    image_data[image] = {
                        "image": image,
                        "size_mb": size_mb,
                        "pull_count": 1,
                        "pull_frequency": 10,  # Pulls per day (estimated)
                        "layers": self._estimate_layers(size_mb)
                    }
                else:
                    image_data[image]["pull_count"] += 1

        # Identify bloated images
        bloated_images = [
            data for data in image_data.values()
            if data["size_mb"] > bloat_threshold_mb
        ]

        total_size_mb = sum(data["size_mb"] for data in image_data.values())

        return {
            "total_images": len(image_data),
            "bloated_images": bloated_images,
            "avg_size_mb": total_size_mb / len(image_data) if image_data else 0,
            "total_size_gb": total_size_mb / 1024
        }

    def _estimate_image_size(self, image: str) -> float:
        """
        Estimate image size based on image name

        In production, query actual size from registry
        """
        # Check if it's a known minimal image
        for base_image, size in self.MINIMAL_IMAGE_SIZES.items():
            if base_image in image.lower():
                return size * 1.5  # Assume some bloat on top of base

        # Default estimates based on common patterns
        if "alpine" in image.lower():
            return 150  # Alpine-based images
        elif "slim" in image.lower():
            return 250  # Slim variants
        elif "node" in image.lower():
            return 900  # Node.js images (notoriously large)
        elif "python" in image.lower():
            return 800  # Python images
        elif "java" in image.lower() or "openjdk" in image.lower():
            return 450  # Java images
        elif "golang" in image.lower() or "go" in image.lower():
            return 700  # Golang images (with build tools)
        else:
            return 600  # Generic estimate

    def _estimate_layers(self, size_mb: float) -> int:
        """Estimate number of layers based on size"""
        if size_mb < 100:
            return 3
        elif size_mb < 500:
            return 8
        elif size_mb < 1000:
            return 15
        else:
            return 25

    def _identify_bloat_reasons(self, image_data: Dict[str, Any]) -> List[str]:
        """
        Identify likely reasons for image bloat

        In production, analyze Dockerfile and layers
        """
        size_mb = image_data["size_mb"]
        image_name = image_data["image"]
        reasons = []

        if size_mb > 2000:
            reasons.append("Extremely large base image")

        if size_mb > 1000:
            reasons.append("Likely includes build tools (not needed for runtime)")

        if "latest" in image_name or not re.search(r':\d+\.\d+', image_name):
            reasons.append("Using 'latest' tag (likely full image, not minimal)")

        if image_data.get("layers", 0) > 20:
            reasons.append("Too many layers (inefficient caching)")

        if "node" in image_name.lower() and size_mb > 400:
            reasons.append("Node.js image includes npm cache")

        if "python" in image_name.lower() and size_mb > 300:
            reasons.append("Python image includes pip cache or .pyc files")

        if size_mb > 500 and "alpine" not in image_name.lower() and "slim" not in image_name.lower():
            reasons.append("Not using minimal base image (alpine/slim)")

        return reasons if reasons else ["General bloat from large dependencies"]

    def _get_optimization_techniques(self, bloat_reasons: List[str]) -> List[str]:
        """Get optimization recommendations based on bloat reasons"""
        techniques = set()

        for reason in bloat_reasons:
            if "build tools" in reason.lower():
                techniques.add("Use multi-stage builds")
                techniques.add("Remove dev dependencies in final stage")

            if "npm cache" in reason.lower():
                techniques.add("Clear npm cache: RUN npm cache clean --force")

            if "pip cache" in reason.lower():
                techniques.add("Use pip --no-cache-dir flag")
                techniques.add("Remove .pyc files: RUN find . -type d -name __pycache__ -exec rm -rf {} +")

            if "alpine" in reason.lower() or "slim" in reason.lower():
                techniques.add("Switch to Alpine-based image")
                techniques.add("Use distroless for production")

            if "layers" in reason.lower():
                techniques.add("Combine RUN commands to reduce layers")
                techniques.add("Use .dockerignore to exclude unnecessary files")

        # Default recommendations
        if not techniques:
            techniques.add("Use multi-stage builds")
            techniques.add("Use .dockerignore file")
            techniques.add("Remove build dependencies after installation")

        return sorted(list(techniques))

    def _calc_storage_savings(self, size_reduction_mb: float) -> Decimal:
        """Calculate monthly ECR storage savings"""
        size_reduction_gb = Decimal(str(size_reduction_mb / 1024))
        return size_reduction_gb * self.ECR_STORAGE_GB_MONTH

    def _calc_transfer_savings(self, size_reduction_mb: float, pulls_per_day: int) -> Decimal:
        """Calculate monthly data transfer savings"""
        size_reduction_gb = Decimal(str(size_reduction_mb / 1024))

        # Assume 70% cross-AZ pulls, 30% internet pulls
        pulls_per_month = pulls_per_day * 30
        cross_az_pulls = pulls_per_month * 0.7
        internet_pulls = pulls_per_month * 0.3

        cross_az_savings = size_reduction_gb * cross_az_pulls * self.CROSS_AZ_TRANSFER_GB
        internet_savings = size_reduction_gb * internet_pulls * self.INTERNET_TRANSFER_GB

        return cross_az_savings + internet_savings

    def _estimate_startup_improvement(self, size_reduction_mb: float) -> int:
        """
        Estimate pod startup time improvement from smaller images

        Rough formula: 100MB reduction = ~5 seconds faster startup
        """
        return int((size_reduction_mb / 100) * 5)

    def _calculate_costs(
        self,
        image_analysis: Dict[str, Any],
        region: str
    ) -> Dict[str, Decimal]:
        """Calculate current ECR and transfer costs"""
        total_size_gb = Decimal(str(image_analysis["total_size_gb"]))

        # Storage cost
        storage_cost = total_size_gb * self.ECR_STORAGE_GB_MONTH

        # Transfer cost (estimate based on typical pull frequency)
        avg_pulls_per_day = 50  # Assumption
        pulls_per_month = avg_pulls_per_day * 30

        # 70% cross-AZ, 30% internet
        cross_az_transfer_gb = total_size_gb * pulls_per_month * Decimal("0.7")
        internet_transfer_gb = total_size_gb * pulls_per_month * Decimal("0.3")

        transfer_cost = (
            cross_az_transfer_gb * self.CROSS_AZ_TRANSFER_GB +
            internet_transfer_gb * self.INTERNET_TRANSFER_GB
        )

        return {
            "storage_cost_monthly": storage_cost,
            "transfer_cost_monthly": transfer_cost,
            "total_monthly_cost": storage_cost + transfer_cost
        }

    def _build_execution_plan(
        self,
        recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build execution plan for image optimization"""
        plan = []

        for idx, rec in enumerate(recommendations, 1):
            plan.append({
                "step": idx,
                "action": "optimize_image",
                "image": rec["image"],
                "description": f"Optimize {rec['image']} (reduce {rec['size_reduction_mb']:.0f}MB)",
                "techniques": rec["optimization_techniques"],
                "expected_savings_annual": rec["savings_annual"],
                "example_dockerfile": self._get_example_dockerfile(rec)
            })

        return plan

    def _get_example_dockerfile(self, rec: Dict[str, Any]) -> str:
        """Generate example optimized Dockerfile"""
        image_name = rec["image"]

        if "node" in image_name.lower():
            return """# Multi-stage build example
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force
COPY . .

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app .
CMD ["node", "server.js"]"""

        elif "python" in image_name.lower():
            return """# Multi-stage build example
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3/site-packages /usr/local/lib/python3/site-packages
COPY . .
RUN find . -type d -name __pycache__ -exec rm -rf {} +
CMD ["python", "app.py"]"""

        else:
            return """# Multi-stage build template
FROM <base>:alpine AS builder
# Build steps here

FROM <base>:alpine
COPY --from=builder /app /app
CMD ["./app"]"""
