"""
Common Schemas for CloudOptim Agentless Architecture

This module contains all shared Pydantic models used across:
- ML Server
- Core Platform
- Admin Frontend (via API responses)

All schemas enforce type safety and validation for cross-component communication.
"""

from .models import (
    ClusterState,
    NodeInfo,
    PodInfo,
    ClusterMetrics,
    NodeMetric,
)

from .requests import (
    DecisionRequest,
    ModelUploadRequest,
    EngineUploadRequest,
    OptimizationTriggerRequest,
)

from .responses import (
    DecisionResponse,
    Recommendation,
    ExecutionStep,
    TaskResult,
    ModelUploadResponse,
    EngineUploadResponse,
)

from .k8s_models import (
    RemoteK8sTask,
    K8sNodeSpec,
    K8sPodSpec,
    K8sDeploymentSpec,
)

from .aws_models import (
    SpotEvent,
    EC2InstanceLaunchRequest,
    EC2InstanceTerminateRequest,
    SpotPriceQuery,
    SpotPriceData,
)

__all__ = [
    # Core models
    "ClusterState",
    "NodeInfo",
    "PodInfo",
    "ClusterMetrics",
    "NodeMetric",

    # Requests
    "DecisionRequest",
    "ModelUploadRequest",
    "EngineUploadRequest",
    "OptimizationTriggerRequest",

    # Responses
    "DecisionResponse",
    "Recommendation",
    "ExecutionStep",
    "TaskResult",
    "ModelUploadResponse",
    "EngineUploadResponse",

    # K8s models
    "RemoteK8sTask",
    "K8sNodeSpec",
    "K8sPodSpec",
    "K8sDeploymentSpec",

    # AWS models
    "SpotEvent",
    "EC2InstanceLaunchRequest",
    "EC2InstanceTerminateRequest",
    "SpotPriceQuery",
    "SpotPriceData",
]
