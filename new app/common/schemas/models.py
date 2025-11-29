"""
Core Data Models for CloudOptim Agentless Architecture

These models represent the fundamental data structures used across
ML Server and Core Platform for cluster state, metrics, and resources.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class HealthStatus(str, Enum):
    """Cluster health status enum"""
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class NodeType(str, Enum):
    """Kubernetes node type enum"""
    SPOT = "spot"
    ON_DEMAND = "on-demand"
    FARGATE = "fargate"


class PodPhase(str, Enum):
    """Kubernetes pod phase enum"""
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class NodeInfo(BaseModel):
    """Individual node information within a cluster"""
    node_name: str = Field(..., description="Kubernetes node name")
    instance_id: str = Field(..., description="AWS EC2 instance ID")
    instance_type: str = Field(..., description="EC2 instance type (e.g., m5.large)")
    availability_zone: str = Field(..., description="AWS availability zone")
    node_type: NodeType = Field(..., description="Spot or on-demand")

    # Resource capacity
    cpu_cores: float = Field(..., description="Total CPU cores on node")
    memory_gb: float = Field(..., description="Total memory in GB")

    # Resource allocation
    cpu_allocated: float = Field(0.0, description="CPU cores allocated to pods")
    memory_allocated_gb: float = Field(0.0, description="Memory allocated to pods in GB")

    # Pod information
    pod_count: int = Field(0, description="Number of pods on this node")

    # Status
    ready: bool = Field(True, description="Node is ready")
    cordoned: bool = Field(False, description="Node is cordoned (unschedulable)")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PodInfo(BaseModel):
    """Individual pod information within a cluster"""
    pod_name: str = Field(..., description="Kubernetes pod name")
    namespace: str = Field(..., description="Kubernetes namespace")
    node_name: str = Field(..., description="Node hosting this pod")
    phase: PodPhase = Field(..., description="Pod phase/status")

    # Resource requests
    cpu_request: float = Field(0.0, description="CPU request in cores")
    memory_request_gb: float = Field(0.0, description="Memory request in GB")

    # Resource usage (if metrics available)
    cpu_usage: Optional[float] = Field(None, description="Actual CPU usage in cores")
    memory_usage_gb: Optional[float] = Field(None, description="Actual memory usage in GB")

    # Container information
    container_count: int = Field(1, description="Number of containers in pod")
    restart_count: int = Field(0, description="Number of restarts")

    # OOMKilled tracking
    oom_killed: bool = Field(False, description="Pod was OOMKilled")
    oom_killed_at: Optional[datetime] = Field(None, description="Time of last OOMKill")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClusterState(BaseModel):
    """
    Complete cluster state snapshot

    This is the primary data structure sent from Core Platform to ML Server
    for all optimization decisions. Contains comprehensive cluster information.
    """
    # Cluster identification
    cluster_id: str = Field(..., description="Unique cluster identifier")
    cluster_name: str = Field(..., description="Kubernetes cluster name")
    region: str = Field(..., description="AWS region (e.g., us-east-1)")

    # Node information
    total_nodes: int = Field(..., description="Total number of nodes")
    spot_nodes: int = Field(0, description="Number of Spot nodes")
    on_demand_nodes: int = Field(0, description="Number of On-Demand nodes")
    fargate_nodes: int = Field(0, description="Number of Fargate nodes")

    # Resource information (cluster-wide)
    total_cpu_cores: float = Field(..., description="Total CPU cores across all nodes")
    total_memory_gb: float = Field(..., description="Total memory in GB across all nodes")
    allocated_cpu_cores: float = Field(..., description="CPU cores allocated to pods")
    allocated_memory_gb: float = Field(..., description="Memory allocated to pods in GB")

    # Pod information
    total_pods: int = Field(..., description="Total number of pods")
    running_pods: int = Field(0, description="Number of running pods")
    pending_pods: int = Field(0, description="Number of pending pods")
    failed_pods: int = Field(0, description="Number of failed pods")

    # Cost information
    current_cost_per_hour: float = Field(..., description="Current hourly cost (USD)")
    baseline_cost_per_hour: float = Field(..., description="Baseline cost if all On-Demand (USD)")

    # Detailed lists (optional, for bin packing and rightsizing)
    nodes: Optional[List[NodeInfo]] = Field(None, description="Detailed node information")
    pods: Optional[List[PodInfo]] = Field(None, description="Detailed pod information")

    # Metadata
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    health_status: HealthStatus = Field(HealthStatus.GREEN, description="Overall cluster health")

    # Additional context
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class NodeMetric(BaseModel):
    """
    Node-level metrics collected from Kubernetes Metrics API

    Used for rightsizing decisions and utilization analysis.
    """
    node_name: str = Field(..., description="Kubernetes node name")
    instance_type: str = Field(..., description="EC2 instance type")
    instance_id: str = Field(..., description="EC2 instance ID")
    availability_zone: str = Field(..., description="Availability zone")
    node_type: NodeType = Field(..., description="Spot or on-demand")

    # Capacity
    cpu_allocatable: float = Field(..., description="CPU cores allocatable to pods")
    memory_allocatable_gb: float = Field(..., description="Memory allocatable to pods in GB")

    # Allocation (requests)
    cpu_allocated: float = Field(0.0, description="CPU cores requested by pods")
    memory_allocated_gb: float = Field(0.0, description="Memory requested by pods in GB")

    # Usage (actual)
    cpu_usage: float = Field(0.0, description="Actual CPU usage in cores")
    memory_usage_gb: float = Field(0.0, description="Actual memory usage in GB")

    # Utilization percentages
    cpu_utilization: float = Field(0.0, description="CPU utilization (0.0 to 1.0)")
    memory_utilization: float = Field(0.0, description="Memory utilization (0.0 to 1.0)")

    # Pod count
    pod_count: int = Field(0, description="Number of pods on this node")

    # Cost
    hourly_price: float = Field(0.0, description="Hourly price for this instance (USD)")

    # Timestamp
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class ClusterMetrics(BaseModel):
    """
    Cluster-wide metrics snapshot

    Collected from Kubernetes Metrics API and used for monitoring,
    rightsizing, and bin packing decisions.
    """
    # Cluster identification
    cluster_id: str = Field(..., description="Unique cluster identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Aggregated metrics
    total_nodes: int = Field(..., description="Total number of nodes")
    spot_nodes: int = Field(0, description="Number of Spot nodes")
    on_demand_nodes: int = Field(0, description="Number of On-Demand nodes")

    total_cpu: float = Field(..., description="Total CPU cores")
    total_memory_gb: float = Field(..., description="Total memory in GB")

    allocated_cpu: float = Field(..., description="CPU allocated to pods")
    allocated_memory_gb: float = Field(..., description="Memory allocated to pods in GB")

    used_cpu: float = Field(0.0, description="Actual CPU usage")
    used_memory_gb: float = Field(0.0, description="Actual memory usage")

    total_pods: int = Field(..., description="Total number of pods")

    # Node-level details
    nodes: List[NodeMetric] = Field(default_factory=list, description="Per-node metrics")

    # Cost calculation
    estimated_cost_per_hour: float = Field(..., description="Estimated hourly cost (USD)")

    # Efficiency metrics
    cpu_efficiency: float = Field(0.0, description="CPU efficiency (used / allocated)")
    memory_efficiency: float = Field(0.0, description="Memory efficiency (used / allocated)")

    # Metadata
    collection_duration_seconds: float = Field(0.0, description="Time to collect metrics")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class OptimizationHistory(BaseModel):
    """
    Record of an optimization execution

    Stored in Core Platform database for auditing and analytics.
    """
    # Identification
    optimization_id: str = Field(..., description="Unique optimization ID")
    cluster_id: str = Field(..., description="Cluster ID")

    # Optimization details
    optimization_type: str = Field(..., description="Type (spot, bin_pack, rightsize, etc.)")
    triggered_by: str = Field(..., description="What triggered this (scheduler, spot_warning, manual)")

    # Execution
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    duration_seconds: float = Field(0.0, description="Execution duration")
    status: str = Field("pending", description="Status (success, failed, partial)")

    # Before/after state
    before_state: ClusterState = Field(..., description="Cluster state before optimization")
    after_state: Optional[ClusterState] = Field(None, description="Cluster state after optimization")

    # Results
    nodes_added: int = Field(0, description="Number of nodes added")
    nodes_removed: int = Field(0, description="Number of nodes removed")
    pods_migrated: int = Field(0, description="Number of pods migrated")

    # Savings
    estimated_monthly_savings: float = Field(0.0, description="Estimated monthly savings (USD)")
    actual_monthly_savings: Optional[float] = Field(None, description="Actual monthly savings (USD)")

    # Errors
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
