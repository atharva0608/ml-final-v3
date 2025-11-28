"""
Decision Engine Module

Contains all 8 CAST AI-compatible decision engines for
agentless Kubernetes cost optimization.

Engines:
1. Spot Optimizer - Select optimal Spot instances using AWS Spot Advisor
2. Bin Packing - Consolidate workloads (Tetris algorithm)
3. Rightsizing - Match instance sizes to workload requirements
4. Office Hours Scheduler - Auto-scale dev/staging environments
5. Ghost Probe Scanner - Detect zombie EC2 instances
6. Zombie Volume Cleanup - Remove unattached EBS volumes
7. Network Optimizer - Optimize cross-AZ traffic
8. OOMKilled Remediation - Auto-fix OOMKilled pods
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

__all__ = [
    "BaseDecisionEngine",
    "SpotOptimizerEngine",
    "BinPackingEngine",
    "RightsizingEngine",
    "OfficeHoursScheduler",
    "GhostProbeScanner",
    "VolumeCleanupEngine",
    "NetworkOptimizerEngine",
    "OOMKilledRemediationEngine"
]
