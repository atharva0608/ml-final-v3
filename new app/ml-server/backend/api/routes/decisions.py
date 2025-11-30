"""
Decision Engine API Routes

Endpoints for all 12 decision engines (8 core + 4 advanced)
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from decimal import Decimal
import logging

# Import all decision engines
from decision_engine import (
    # Core engines
    SpotOptimizerEngine,
    BinPackingEngine,
    RightsizingEngine,
    OfficeHoursScheduler,
    GhostProbeScanner,
    VolumeCleanupEngine,
    NetworkOptimizerEngine,
    OOMKilledRemediationEngine,
    # Advanced engines
    IPv4CostTrackerEngine,
    ImageBloatAnalyzerEngine,
    ShadowITTrackerEngine,
    NoisyNeighborDetectorEngine
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Pydantic Schemas
# ============================================================================

class DecisionRequest(BaseModel):
    """Base decision request schema"""
    cluster_state: Dict[str, Any] = Field(
        ...,
        description="Current cluster state (nodes, pods, metrics)",
        example={
            "nodes": [{"name": "node-1", "instance_type": "m5.large"}],
            "pods": [{"name": "pod-1", "namespace": "default"}],
            "metrics": {"cpu_usage": 0.45}
        }
    )
    requirements: Dict[str, Any] = Field(
        ...,
        description="Decision-specific requirements",
        example={"region": "us-east-1", "cpu": 2, "memory": 4}
    )
    constraints: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional safety constraints",
        example={"max_interruption_risk": 0.15}
    )

class DecisionResponse(BaseModel):
    """Standard decision response"""
    engine: str = Field(..., description="Decision engine name")
    recommendations: List[Dict[str, Any]] = Field(..., description="List of recommendations")
    confidence_score: float = Field(..., description="Confidence in decision (0.0-1.0)")
    estimated_savings: float = Field(..., description="Estimated monthly savings (USD)")
    execution_plan: List[Dict[str, Any]] = Field(..., description="Step-by-step execution plan")
    metadata: Dict[str, Any] = Field(..., description="Additional metadata")

# ============================================================================
# Core Decision Engine Endpoints (8)
# ============================================================================

@router.post(
    "/decision/spot-optimize",
    response_model=DecisionResponse,
    summary="Spot Instance Optimization",
    description="Select optimal Spot instances using AWS Spot Advisor data"
)
async def spot_optimize(request: DecisionRequest):
    """
    Spot Optimizer Engine

    Recommends optimal Spot instances based on:
    - AWS Spot Advisor interruption rates
    - Historical price volatility
    - Current price vs On-Demand gap
    - Workload requirements
    """
    try:
        engine = SpotOptimizerEngine()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Spot optimization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Spot optimization failed: {str(e)}"
        )

@router.post(
    "/decision/bin-pack",
    response_model=DecisionResponse,
    summary="Bin Packing (Tetris Algorithm)",
    description="Consolidate workloads to minimize node count"
)
async def bin_pack(request: DecisionRequest):
    """Bin Packing Engine - Consolidate workloads (Tetris algorithm)"""
    try:
        engine = BinPackingEngine()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Bin packing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bin packing failed: {str(e)}"
        )

@router.post(
    "/decision/rightsize",
    response_model=DecisionResponse,
    summary="Instance Rightsizing",
    description="Match instance sizes to workload requirements"
)
async def rightsize(request: DecisionRequest):
    """Rightsizing Engine - Match instance sizes to workload"""
    try:
        engine = RightsizingEngine()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Rightsizing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rightsizing failed: {str(e)}"
        )

@router.post(
    "/decision/office-hours",
    response_model=DecisionResponse,
    summary="Office Hours Scheduler",
    description="Auto-scale dev/staging environments during business hours"
)
async def office_hours(request: DecisionRequest):
    """Office Hours Scheduler - Auto-scale non-prod environments"""
    try:
        engine = OfficeHoursScheduler()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Office hours scheduling failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Office hours scheduling failed: {str(e)}"
        )

@router.post(
    "/decision/ghost-probe",
    response_model=DecisionResponse,
    summary="Ghost Probe Scanner",
    description="Detect zombie EC2 instances not in Kubernetes"
)
async def ghost_probe(request: DecisionRequest):
    """Ghost Probe Scanner - Detect zombie EC2 instances"""
    try:
        engine = GhostProbeScanner()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Ghost probe scanning failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ghost probe scanning failed: {str(e)}"
        )

@router.post(
    "/decision/volume-cleanup",
    response_model=DecisionResponse,
    summary="Zombie Volume Cleanup",
    description="Identify and remove unattached EBS volumes"
)
async def volume_cleanup(request: DecisionRequest):
    """Volume Cleanup Engine - Remove unattached EBS volumes"""
    try:
        engine = VolumeCleanupEngine()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Volume cleanup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Volume cleanup failed: {str(e)}"
        )

@router.post(
    "/decision/network-optimize",
    response_model=DecisionResponse,
    summary="Network Optimizer",
    description="Optimize cross-AZ traffic to reduce data transfer costs"
)
async def network_optimize(request: DecisionRequest):
    """Network Optimizer - Reduce cross-AZ traffic costs"""
    try:
        engine = NetworkOptimizerEngine()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Network optimization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Network optimization failed: {str(e)}"
        )

@router.post(
    "/decision/oomkilled-remediation",
    response_model=DecisionResponse,
    summary="OOMKilled Remediation",
    description="Auto-fix OOMKilled pods by adjusting resource requests"
)
async def oomkilled_remediation(request: DecisionRequest):
    """OOMKilled Remediation - Auto-fix out-of-memory pod crashes"""
    try:
        engine = OOMKilledRemediationEngine()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"OOMKilled remediation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OOMKilled remediation failed: {str(e)}"
        )

# ============================================================================
# Advanced Decision Engine Endpoints (4)
# ============================================================================

@router.post(
    "/decision/ipv4-cost-tracking",
    response_model=DecisionResponse,
    summary="IPv4 Cost Tracker (NEW AWS Charge Feb 2024)",
    description="Track public IPv4 costs and recommend optimizations"
)
async def ipv4_cost_tracking(request: DecisionRequest):
    """
    IPv4 Cost Tracker Engine

    Tracks AWS public IPv4 costs ($0.005/hr since Feb 2024) and recommends:
    - Release unused Elastic IPs
    - IPv6 migration (free)
    - NAT Gateway consolidation
    - ALB/NLB IP sharing

    Value: Find $500-2000/year in hidden costs
    """
    try:
        engine = IPv4CostTrackerEngine()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"IPv4 cost tracking failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"IPv4 cost tracking failed: {str(e)}"
        )

@router.post(
    "/decision/image-bloat-analysis",
    response_model=DecisionResponse,
    summary="Container Image Bloat Tax Calculator",
    description="Analyze container image sizes and calculate bloat tax"
)
async def image_bloat_analysis(request: DecisionRequest):
    """
    Image Bloat Analyzer Engine

    Detects oversized container images and calculates costs:
    - ECR storage costs
    - Cross-AZ transfer costs
    - Internet egress costs
    - Pod startup time impact

    Value: 10-40% savings on transfer costs
    Viral: "Your image was 92% bloat!"
    """
    try:
        engine = ImageBloatAnalyzerEngine()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Image bloat analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image bloat analysis failed: {str(e)}"
        )

@router.post(
    "/decision/shadow-it-detection",
    response_model=DecisionResponse,
    summary="Shadow IT Tracker",
    description="Find AWS resources NOT managed by Kubernetes"
)
async def shadow_it_detection(request: DecisionRequest):
    """
    Shadow IT Tracker Engine

    Detects AWS resources not managed by Kubernetes:
    - EC2 instances not in any cluster
    - EBS volumes not attached to K8s nodes
    - Load balancers not in Ingress
    - Shows who created each resource (IAM compliance)

    Value: Find 10-30% hidden costs ($150-750/month)
    """
    try:
        engine = ShadowITTrackerEngine()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Shadow IT detection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Shadow IT detection failed: {str(e)}"
        )

@router.post(
    "/decision/noisy-neighbor-detection",
    response_model=DecisionResponse,
    summary="Noisy Neighbor Cost Detector",
    description="Detect pods causing excessive network traffic"
)
async def noisy_neighbor_detection(request: DecisionRequest):
    """
    Noisy Neighbor Detector Engine

    Identifies pods causing excessive network traffic:
    - Bandwidth >10x cluster average
    - High cross-AZ traffic
    - High internet egress
    - Estimates performance impact on other services

    Value: 60% network cost reduction potential
    Unique: Connects performance problems to costs
    """
    try:
        engine = NoisyNeighborDetectorEngine()
        result = engine.decide(
            cluster_state=request.cluster_state,
            requirements=request.requirements,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Noisy neighbor detection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Noisy neighbor detection failed: {str(e)}"
        )

# ============================================================================
# Batch Decision Endpoint
# ============================================================================

class BatchDecisionRequest(BaseModel):
    """Request multiple decisions at once"""
    cluster_state: Dict[str, Any]
    requirements: Dict[str, Any]
    constraints: Optional[Dict[str, Any]] = None
    engines: List[str] = Field(
        ...,
        description="List of engine names to run",
        example=["spot_optimize", "bin_pack", "ipv4_cost_tracking"]
    )

@router.post(
    "/decision/batch",
    summary="Run Multiple Decision Engines",
    description="Execute multiple decision engines in a single request"
)
async def batch_decisions(request: BatchDecisionRequest):
    """
    Run multiple decision engines and return combined results

    Useful for dashboard views that show all optimization opportunities
    """
    engine_map = {
        "spot_optimize": SpotOptimizerEngine,
        "bin_pack": BinPackingEngine,
        "rightsize": RightsizingEngine,
        "office_hours": OfficeHoursScheduler,
        "ghost_probe": GhostProbeScanner,
        "volume_cleanup": VolumeCleanupEngine,
        "network_optimize": NetworkOptimizerEngine,
        "oomkilled_remediation": OOMKilledRemediationEngine,
        "ipv4_cost_tracking": IPv4CostTrackerEngine,
        "image_bloat_analysis": ImageBloatAnalyzerEngine,
        "shadow_it_detection": ShadowITTrackerEngine,
        "noisy_neighbor_detection": NoisyNeighborDetectorEngine
    }

    results = {}
    errors = {}

    for engine_name in request.engines:
        if engine_name not in engine_map:
            errors[engine_name] = f"Unknown engine: {engine_name}"
            continue

        try:
            engine_class = engine_map[engine_name]
            engine = engine_class()
            result = engine.decide(
                cluster_state=request.cluster_state,
                requirements=request.requirements,
                constraints=request.constraints
            )
            results[engine_name] = result
        except Exception as e:
            logger.error(f"Batch decision failed for {engine_name}: {e}", exc_info=True)
            errors[engine_name] = str(e)

    # Calculate total savings
    total_savings = sum(
        float(result.get("estimated_savings", 0))
        for result in results.values()
    )

    return {
        "results": results,
        "errors": errors if errors else None,
        "summary": {
            "engines_run": len(results),
            "engines_failed": len(errors),
            "total_monthly_savings": round(total_savings, 2),
            "total_annual_savings": round(total_savings * 12, 2)
        }
    }
