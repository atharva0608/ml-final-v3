"""
API Request Schemas for CloudOptim Agentless Architecture

All request models sent from Core Platform to ML Server
or from Admin Frontend to Core Platform.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from .models import ClusterState


class DecisionRequest(BaseModel):
    """
    Request sent from Core Platform to ML Server for optimization decisions

    Flow: Core Platform → ML Server decision endpoint
    Used by all 8 decision engines (spot, bin_pack, rightsize, etc.)
    """
    # Request identification
    request_id: str = Field(..., description="Unique request ID (UUID)")
    cluster_id: str = Field(..., description="Cluster ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Decision type
    decision_type: str = Field(
        ...,
        description="Decision engine type (spot_optimize, bin_pack, rightsize, schedule, ghost_probe, volume_cleanup, network_optimize, oomkilled_remediate)"
    )

    # Current state
    current_state: ClusterState = Field(..., description="Current cluster state snapshot")

    # Requirements (specific to decision type)
    requirements: Dict[str, Any] = Field(
        default_factory=dict,
        description="Decision-specific requirements (e.g., cpu_required, memory_required)"
    )

    # Constraints (customer-defined limits)
    constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optimization constraints (e.g., max_spot_percentage: 0.80)"
    )

    # Context
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (triggered_by, priority, etc.)"
    )


class ModelUploadRequest(BaseModel):
    """
    Request to upload a pre-trained ML model to ML Server

    Flow: Admin Frontend → Core Platform → ML Server
    """
    # Model metadata
    model_name: str = Field(..., description="Model name (e.g., spot_predictor_v2)")
    model_version: str = Field(..., description="Model version (e.g., 2.1.0)")
    model_type: str = Field(..., description="Model type (spot_prediction, bin_packing, etc.)")

    # Training metadata
    trained_until_date: str = Field(..., description="Last date in training data (YYYY-MM-DD)")
    framework: str = Field("sklearn", description="ML framework (sklearn, xgboost, lightgbm)")

    # Decision engine association
    decision_engine: str = Field(..., description="Associated decision engine (spot_optimizer, bin_packing, etc.)")

    # File metadata (actual file uploaded separately as multipart/form-data)
    file_size_mb: Optional[float] = Field(None, description="Model file size in MB")
    checksum: Optional[str] = Field(None, description="SHA256 checksum of model file")

    # Activation
    activate_immediately: bool = Field(False, description="Activate this model immediately after upload")

    # Metadata
    description: Optional[str] = Field(None, description="Model description")
    tags: Dict[str, str] = Field(default_factory=dict, description="Custom tags")


class EngineUploadRequest(BaseModel):
    """
    Request to upload a custom decision engine module to ML Server

    Flow: Admin Frontend → Core Platform → ML Server
    Allows customers to upload custom decision logic.
    """
    # Engine metadata
    engine_name: str = Field(..., description="Engine name (e.g., custom_spot_optimizer)")
    engine_version: str = Field(..., description="Engine version (e.g., 1.0.0)")
    engine_type: str = Field(..., description="Engine type (spot, bin_pack, rightsize, etc.)")

    # Implementation details
    language: str = Field("python", description="Implementation language (python)")
    framework_version: str = Field("3.11", description="Python version required")

    # File metadata (actual file uploaded separately as multipart/form-data)
    file_size_kb: Optional[float] = Field(None, description="Engine file size in KB")
    checksum: Optional[str] = Field(None, description="SHA256 checksum of engine file")

    # Activation
    activate_immediately: bool = Field(False, description="Activate this engine immediately after upload")

    # Safety and validation
    requires_approval: bool = Field(True, description="Requires admin approval before activation")

    # Metadata
    description: Optional[str] = Field(None, description="Engine description")
    author: Optional[str] = Field(None, description="Engine author")


class OptimizationTriggerRequest(BaseModel):
    """
    Request to manually trigger an optimization

    Flow: Admin Frontend → Core Platform
    User-initiated optimization (bypassing normal schedule).
    """
    # Cluster identification
    cluster_id: str = Field(..., description="Cluster ID to optimize")

    # Optimization type
    optimization_type: str = Field(
        ...,
        description="Optimization type (spot, bin_pack, rightsize, schedule, all)"
    )

    # Options
    dry_run: bool = Field(False, description="Simulate without executing (dry run)")
    force: bool = Field(False, description="Force optimization even if recent optimization exists")

    # Constraints override
    constraints_override: Optional[Dict[str, Any]] = Field(
        None,
        description="Override default constraints for this optimization"
    )

    # Priority
    priority: int = Field(5, description="Execution priority (1=highest, 10=lowest)")

    # Metadata
    triggered_by: str = Field("manual", description="Who/what triggered this")
    reason: Optional[str] = Field(None, description="Reason for triggering")


class GapFillerAnalyzeRequest(BaseModel):
    """
    Request to analyze data gaps for a model

    Flow: Admin Frontend → ML Server
    Identifies missing data between model training date and today.
    """
    # Model identification
    model_id: str = Field(..., description="Model ID to analyze")

    # Analysis options
    target_date: Optional[str] = Field(None, description="Target date (YYYY-MM-DD), defaults to today")
    instance_types: Optional[List[str]] = Field(None, description="Instance types to check (all if None)")
    regions: Optional[List[str]] = Field(None, description="Regions to check (all if None)")


class GapFillerFillRequest(BaseModel):
    """
    Request to fill data gaps for a model

    Flow: Admin Frontend → ML Server
    Fetches missing AWS pricing data and processes it for model readiness.
    """
    # Model identification
    model_id: str = Field(..., description="Model ID to fill gaps for")

    # Gap filling options
    target_date: Optional[str] = Field(None, description="Target date (YYYY-MM-DD), defaults to today")
    instance_types: Optional[List[str]] = Field(None, description="Instance types to fill (all if None)")
    regions: Optional[List[str]] = Field(None, description="Regions to fill (all if None)")

    # Processing options
    fetch_spot_prices: bool = Field(True, description="Fetch Spot price history")
    fetch_on_demand_prices: bool = Field(True, description="Fetch On-Demand prices")
    fetch_spot_advisor: bool = Field(True, description="Fetch AWS Spot Advisor data")

    # Priority
    priority: int = Field(5, description="Job priority (1=highest, 10=lowest)")

    # Metadata
    triggered_by: str = Field("manual", description="Who/what triggered this")


class CustomerOnboardingRequest(BaseModel):
    """
    Request to onboard a new customer

    Flow: Admin Frontend → Core Platform
    Sets up AWS EventBridge, SQS, and K8s access for a new customer.
    """
    # Customer information
    customer_name: str = Field(..., description="Customer company name")
    customer_email: str = Field(..., description="Customer contact email")

    # AWS account details
    aws_account_id: str = Field(..., description="Customer AWS account ID")
    aws_regions: List[str] = Field(..., description="AWS regions to monitor")

    # Kubernetes cluster details
    cluster_name: str = Field(..., description="EKS cluster name")
    cluster_region: str = Field(..., description="EKS cluster region")
    kubeconfig: str = Field(..., description="Base64-encoded kubeconfig file")

    # EventBridge + SQS setup
    create_eventbridge_rule: bool = Field(True, description="Auto-create EventBridge rule")
    create_sqs_queue: bool = Field(True, description="Auto-create SQS queue")

    # Optimization preferences
    enable_spot_optimization: bool = Field(True, description="Enable Spot instance optimization")
    enable_bin_packing: bool = Field(True, description="Enable bin packing")
    enable_rightsizing: bool = Field(True, description="Enable rightsizing")
    max_spot_percentage: float = Field(0.80, description="Maximum Spot percentage (0.0 to 1.0)")

    # Metadata
    notes: Optional[str] = Field(None, description="Onboarding notes")


class ClusterUpdateRequest(BaseModel):
    """
    Request to update cluster configuration

    Flow: Admin Frontend → Core Platform
    """
    # Cluster identification
    cluster_id: str = Field(..., description="Cluster ID")

    # Update fields
    cluster_name: Optional[str] = Field(None, description="Updated cluster name")
    max_spot_percentage: Optional[float] = Field(None, description="Updated max Spot percentage")

    # Optimization enablement
    enable_spot_optimization: Optional[bool] = Field(None, description="Enable/disable Spot optimization")
    enable_bin_packing: Optional[bool] = Field(None, description="Enable/disable bin packing")
    enable_rightsizing: Optional[bool] = Field(None, description="Enable/disable rightsizing")
    enable_scheduler: Optional[bool] = Field(None, description="Enable/disable office hours scheduler")

    # Metadata
    updated_by: str = Field(..., description="Who made this update")
    reason: Optional[str] = Field(None, description="Reason for update")
