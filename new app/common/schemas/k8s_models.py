"""
Kubernetes Models for CloudOptim Agentless Architecture

Schemas for remote Kubernetes API operations.
All operations via HTTPS remote API calls (NO DaemonSets).
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class RemoteK8sTask(BaseModel):
    """
    Task for remote Kubernetes API operations

    Flow: Core Platform creates task → Executes via remote K8s API → Records result
    Used for all K8s operations: drain, cordon, scale, etc.
    """
    # Task identification
    task_id: str = Field(..., description="Unique task ID (UUID)")
    cluster_id: str = Field(..., description="Cluster ID")
    task_type: str = Field(
        ...,
        description="Task type (drain_node, cordon_node, uncordon_node, scale_deployment, delete_pod, etc.)"
    )

    # Task parameters
    parameters: Dict[str, Any] = Field(
        ...,
        description="Task-specific parameters (e.g., node_name, grace_period_seconds)"
    )

    # Priority and deadline
    priority: int = Field(5, description="Task priority (1=highest, 10=lowest)")
    deadline: datetime = Field(..., description="Task must complete by this time")

    # Retry configuration
    max_retries: int = Field(3, description="Maximum retry attempts")
    retry_count: int = Field(0, description="Current retry attempt")

    # Status
    status: str = Field("pending", description="Status (pending, in_progress, completed, failed, cancelled)")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(..., description="Service/user that created this task")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class K8sNodeSpec(BaseModel):
    """
    Kubernetes node specification

    Used for node operations via remote K8s API.
    """
    # Node identification
    node_name: str = Field(..., description="Kubernetes node name")
    instance_id: str = Field(..., description="EC2 instance ID")

    # Node details
    instance_type: str = Field(..., description="EC2 instance type")
    availability_zone: str = Field(..., description="Availability zone")
    node_type: str = Field(..., description="Spot or on-demand")

    # Capacity
    cpu_capacity: float = Field(..., description="Total CPU cores")
    memory_capacity_gb: float = Field(..., description="Total memory in GB")
    pod_capacity: int = Field(..., description="Maximum pod capacity")

    # Allocation
    cpu_allocatable: float = Field(..., description="CPU allocatable to pods")
    memory_allocatable_gb: float = Field(..., description="Memory allocatable to pods")

    # Status
    ready: bool = Field(True, description="Node is ready")
    cordoned: bool = Field(False, description="Node is cordoned (unschedulable)")
    taints: List[Dict[str, str]] = Field(default_factory=list, description="Node taints")

    # Labels
    labels: Dict[str, str] = Field(default_factory=dict, description="Node labels")

    # Timestamps
    created_at: datetime = Field(..., description="Node creation time")


class K8sPodSpec(BaseModel):
    """
    Kubernetes pod specification

    Used for pod operations via remote K8s API.
    """
    # Pod identification
    pod_name: str = Field(..., description="Pod name")
    namespace: str = Field(..., description="Namespace")
    pod_uid: str = Field(..., description="Pod UID")

    # Scheduling
    node_name: str = Field(..., description="Node hosting this pod")
    priority_class: Optional[str] = Field(None, description="Priority class")

    # Resource requests
    cpu_request: float = Field(0.0, description="CPU request in cores")
    memory_request_gb: float = Field(0.0, description="Memory request in GB")
    cpu_limit: Optional[float] = Field(None, description="CPU limit in cores")
    memory_limit_gb: Optional[float] = Field(None, description="Memory limit in GB")

    # Phase
    phase: str = Field(..., description="Pod phase (Pending, Running, Succeeded, Failed, Unknown)")

    # Container information
    containers: List[Dict[str, Any]] = Field(default_factory=list, description="Container specs")
    restart_count: int = Field(0, description="Total restart count across containers")

    # OOMKilled tracking
    oom_killed: bool = Field(False, description="Pod was OOMKilled")
    oom_killed_at: Optional[datetime] = Field(None, description="Last OOMKill time")

    # Labels and annotations
    labels: Dict[str, str] = Field(default_factory=dict, description="Pod labels")
    annotations: Dict[str, str] = Field(default_factory=dict, description="Pod annotations")

    # Ownership
    owner_kind: Optional[str] = Field(None, description="Owner kind (Deployment, StatefulSet, etc.)")
    owner_name: Optional[str] = Field(None, description="Owner name")

    # Timestamps
    created_at: datetime = Field(..., description="Pod creation time")


class K8sDeploymentSpec(BaseModel):
    """
    Kubernetes deployment specification

    Used for deployment operations via remote K8s API.
    """
    # Deployment identification
    deployment_name: str = Field(..., description="Deployment name")
    namespace: str = Field(..., description="Namespace")
    deployment_uid: str = Field(..., description="Deployment UID")

    # Replicas
    desired_replicas: int = Field(..., description="Desired replica count")
    current_replicas: int = Field(..., description="Current replica count")
    ready_replicas: int = Field(0, description="Ready replica count")
    available_replicas: int = Field(0, description="Available replica count")

    # Pod template
    pod_template: K8sPodSpec = Field(..., description="Pod template spec")

    # Rollout status
    rollout_status: str = Field("progressing", description="Rollout status (progressing, completed, failed)")

    # Labels and selectors
    labels: Dict[str, str] = Field(default_factory=dict, description="Deployment labels")
    selectors: Dict[str, str] = Field(default_factory=dict, description="Pod selectors")

    # Timestamps
    created_at: datetime = Field(..., description="Deployment creation time")


class K8sDrainRequest(BaseModel):
    """
    Request to drain a Kubernetes node via remote API

    Flow: Core Platform → Remote K8s API
    Used for graceful node shutdown (e.g., Spot interruption).
    """
    # Node identification
    node_name: str = Field(..., description="Node to drain")
    cluster_id: str = Field(..., description="Cluster ID")

    # Drain parameters
    grace_period_seconds: int = Field(90, description="Pod grace period (seconds)")
    timeout_seconds: int = Field(600, description="Maximum drain time (seconds)")

    # Options
    ignore_daemonsets: bool = Field(True, description="Ignore DaemonSet pods")
    delete_emptydir_data: bool = Field(True, description="Delete emptyDir data")
    force: bool = Field(False, description="Force deletion if pod doesn't respect grace period")

    # Safety
    skip_wait_for_delete: bool = Field(False, description="Skip waiting for pod deletion")
    disable_eviction: bool = Field(False, description="Disable eviction API, use delete")

    # Metadata
    reason: str = Field(..., description="Reason for draining (e.g., spot_interruption)")
    triggered_by: str = Field(..., description="What triggered this drain")


class K8sCordonRequest(BaseModel):
    """
    Request to cordon a Kubernetes node via remote API

    Flow: Core Platform → Remote K8s API
    Makes node unschedulable.
    """
    # Node identification
    node_name: str = Field(..., description="Node to cordon")
    cluster_id: str = Field(..., description="Cluster ID")

    # Options
    reason: str = Field(..., description="Reason for cordoning")


class K8sScaleRequest(BaseModel):
    """
    Request to scale a deployment via remote API

    Flow: Core Platform → Remote K8s API
    Used for Office Hours Scheduler feature.
    """
    # Deployment identification
    deployment_name: str = Field(..., description="Deployment to scale")
    namespace: str = Field(..., description="Namespace")
    cluster_id: str = Field(..., description="Cluster ID")

    # Scale parameters
    replicas: int = Field(..., description="Target replica count")

    # Metadata
    reason: str = Field(..., description="Reason for scaling")
    triggered_by: str = Field(..., description="What triggered this scale")


class K8sEvictionRequest(BaseModel):
    """
    Request to evict a pod via remote Kubernetes Eviction API

    Flow: Core Platform → Remote K8s API
    Preferred method for graceful pod removal (respects PDB).
    """
    # Pod identification
    pod_name: str = Field(..., description="Pod to evict")
    namespace: str = Field(..., description="Namespace")
    cluster_id: str = Field(..., description="Cluster ID")

    # Eviction parameters
    grace_period_seconds: int = Field(90, description="Grace period (seconds)")

    # Options
    respect_pdb: bool = Field(True, description="Respect PodDisruptionBudget")

    # Metadata
    reason: str = Field(..., description="Reason for eviction")


class K8sNodeMetricsResponse(BaseModel):
    """
    Response from Kubernetes Metrics API (remote)

    Flow: Remote K8s Metrics API → Core Platform
    Used for rightsizing and bin packing decisions.
    """
    # Node identification
    node_name: str = Field(..., description="Node name")

    # Timestamp
    timestamp: datetime = Field(..., description="Metrics timestamp")

    # CPU metrics
    cpu_usage_cores: float = Field(..., description="CPU usage in cores")
    cpu_usage_percentage: float = Field(..., description="CPU usage percentage (0.0 to 1.0)")

    # Memory metrics
    memory_usage_bytes: int = Field(..., description="Memory usage in bytes")
    memory_usage_gb: float = Field(..., description="Memory usage in GB")
    memory_usage_percentage: float = Field(..., description="Memory usage percentage (0.0 to 1.0)")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metrics")


class K8sPodMetricsResponse(BaseModel):
    """
    Response from Kubernetes Pod Metrics API (remote)

    Flow: Remote K8s Metrics API → Core Platform
    Used for workload rightsizing.
    """
    # Pod identification
    pod_name: str = Field(..., description="Pod name")
    namespace: str = Field(..., description="Namespace")

    # Timestamp
    timestamp: datetime = Field(..., description="Metrics timestamp")

    # Container metrics
    containers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Per-container metrics (cpu_usage_cores, memory_usage_bytes)"
    )

    # Aggregated metrics
    total_cpu_usage_cores: float = Field(0.0, description="Total CPU usage across containers")
    total_memory_usage_gb: float = Field(0.0, description="Total memory usage across containers")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metrics")
