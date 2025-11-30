"""
Decision Engine Module

Contains 12 decision engines for agentless Kubernetes cost optimization:

Core Engines (8 CAST AI-compatible):
1. Spot Optimizer - Select optimal Spot instances using AWS Spot Advisor
2. Bin Packing - Consolidate workloads (Tetris algorithm)
3. Rightsizing - Match instance sizes to workload requirements
4. Office Hours Scheduler - Auto-scale dev/staging environments
5. Ghost Probe Scanner - Detect zombie EC2 instances
6. Zombie Volume Cleanup - Remove unattached EBS volumes
7. Network Optimizer - Optimize cross-AZ traffic
8. OOMKilled Remediation - Auto-fix OOMKilled pods

Advanced Features (4 unique engines):
9. IPv4 Cost Tracker - Track public IPv4 costs (NEW AWS charge Feb 2024)
10. Image Bloat Analyzer - Detect oversized container images
11. Shadow IT Tracker - Find AWS resources NOT in Kubernetes
12. Noisy Neighbor Detector - Detect pods causing network congestion
"""

from .base_engine import BaseDecisionEngine
from .spot_optimizer import SpotOptimizerEngine
from .bin_packing import BinPackingEngine
from .rightsizing import RightsizingEngine
from .scheduler import OfficeHoursScheduler
from .ghost_probe import GhostProbeScanner
from .volume_cleanup import VolumeCleanupEngine
from .network_optimizer import NetworkOptimizerEngine
from .oomkilled_remediation import OOMKilledRemediationEngine

# Advanced feature engines
from .ipv4_cost_tracker import IPv4CostTrackerEngine
from .image_bloat_analyzer import ImageBloatAnalyzerEngine
from .shadow_it_tracker import ShadowITTrackerEngine
from .noisy_neighbor_detector import NoisyNeighborDetectorEngine

__all__ = [
    # Base
    "BaseDecisionEngine",
    # Core engines
    "SpotOptimizerEngine",
    "BinPackingEngine",
    "RightsizingEngine",
    "OfficeHoursScheduler",
    "GhostProbeScanner",
    "VolumeCleanupEngine",
    "NetworkOptimizerEngine",
    "OOMKilledRemediationEngine",
    # Advanced engines
    "IPv4CostTrackerEngine",
    "ImageBloatAnalyzerEngine",
    "ShadowITTrackerEngine",
    "NoisyNeighborDetectorEngine"
]
