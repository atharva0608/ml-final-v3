"""
API Response Schemas for CloudOptim Agentless Architecture

All response models returned from ML Server to Core Platform
or from Core Platform to Admin Frontend.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class Recommendation(BaseModel):
    """
    Single optimization recommendation

    Part of DecisionResponse, represents one possible option
    (e.g., one instance type to use for Spot optimization).
    """
    # Instance details
    instance_type: str = Field(..., description="EC2 instance type (e.g., m5.large)")
    node_count: int = Field(..., description="Number of nodes of this type")
    availability_zone: Optional[str] = Field(None, description="Preferred AZ")

    # Risk and pricing
    risk_score: float = Field(..., description="Risk score (0.0 to 1.0, lower is better)")
    hourly_price: float = Field(..., description="Hourly price per instance (USD)")
    monthly_cost: float = Field(..., description="Total monthly cost for this option (USD)")

    # Savings
    monthly_savings: float = Field(..., description="Monthly savings vs baseline (USD)")
    savings_percentage: float = Field(..., description="Savings percentage (0.0 to 1.0)")

    # Confidence
    confidence_score: float = Field(..., description="Confidence in this recommendation (0.0 to 1.0)")

    # Metadata
    reason: Optional[str] = Field(None, description="Why this was recommended")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional details")


class ExecutionStep(BaseModel):
    """
    Single step in an optimization execution plan

    Part of DecisionResponse, defines what Core Platform should do.
    """
    # Step identification
    step: int = Field(..., description="Step number (execution order)")
    action: str = Field(
        ...,
        description="Action type (launch_spot_instances, drain_node, terminate_instance, cordon_node, etc.)"
    )

    # Action parameters
    parameters: Dict[str, Any] = Field(..., description="Action-specific parameters")

    # Timing
    delay_seconds: int = Field(0, description="Delay before executing this step (seconds)")
    timeout_seconds: int = Field(300, description="Maximum time for this step (seconds)")

    # Safety checks
    requires_confirmation: bool = Field(False, description="Requires manual confirmation")
    rollback_on_failure: bool = Field(True, description="Rollback if this step fails")

    # Description
    description: str = Field(..., description="Human-readable description of this step")


class DecisionResponse(BaseModel):
    """
    Response from ML Server containing optimization recommendations

    Flow: ML Server → Core Platform
    This is the primary response for all decision engine requests.
    """
    # Request correlation
    request_id: str = Field(..., description="Correlates to DecisionRequest.request_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    decision_type: str = Field(..., description="Decision type (spot_optimize, bin_pack, etc.)")

    # Recommendations
    recommendations: List[Recommendation] = Field(
        default_factory=list,
        description="List of optimization recommendations (ordered by preference)"
    )

    # Confidence and savings
    confidence_score: float = Field(..., description="Overall confidence (0.0 to 1.0)")
    estimated_savings: float = Field(..., description="Estimated monthly savings (USD)")

    # Risk assessment
    risk_assessment: Dict[str, Any] = Field(
        default_factory=dict,
        description="Risk analysis (interruption_probability, fallback_plan, etc.)"
    )

    # Execution plan
    execution_plan: List[ExecutionStep] = Field(
        default_factory=list,
        description="Step-by-step execution plan for Core Platform"
    )

    # Day Zero support
    uses_fallback: bool = Field(False, description="True if using Day Zero fallback logic")
    data_quality_score: float = Field(1.0, description="Quality of data used (0.0 to 1.0)")

    # Metadata
    model_version: Optional[str] = Field(None, description="Model version used")
    engine_version: Optional[str] = Field(None, description="Engine version used")
    processing_time_ms: float = Field(0.0, description="Time to process request (milliseconds)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TaskResult(BaseModel):
    """
    Result of a task execution

    Flow: Core Platform internal (after remote K8s API or AWS API call)
    """
    # Task identification
    task_id: str = Field(..., description="Unique task ID (UUID)")
    cluster_id: str = Field(..., description="Cluster ID")
    task_type: str = Field(..., description="Task type (drain_node, launch_instance, etc.)")

    # Execution status
    status: str = Field(..., description="Status (success, failed, timeout, cancelled)")

    # Execution details
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    duration_seconds: float = Field(0.0, description="Execution duration in seconds")

    # Logs and errors
    logs: str = Field("", description="Execution logs")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[str] = Field(None, description="Error code if failed")

    # Results
    result_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific result data (e.g., new_instance_id)"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ModelUploadResponse(BaseModel):
    """
    Response after uploading a model to ML Server

    Flow: ML Server → Core Platform → Admin Frontend
    """
    # Model identification
    model_id: str = Field(..., description="Unique model ID (UUID)")
    model_name: str = Field(..., description="Model name")
    model_version: str = Field(..., description="Model version")

    # Upload details
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    file_size_mb: float = Field(..., description="Model file size in MB")
    checksum: str = Field(..., description="SHA256 checksum")

    # Training metadata
    trained_until_date: str = Field(..., description="Last date in training data (YYYY-MM-DD)")
    framework: str = Field(..., description="ML framework")

    # Status
    active: bool = Field(..., description="True if this model is active")

    # Gap analysis
    data_gap_days: int = Field(0, description="Number of days of data gap")
    requires_gap_fill: bool = Field(False, description="True if gap filling is required")

    # Metadata
    storage_path: str = Field(..., description="Server-side storage path")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class EngineUploadResponse(BaseModel):
    """
    Response after uploading a decision engine to ML Server

    Flow: ML Server → Core Platform → Admin Frontend
    """
    # Engine identification
    engine_id: str = Field(..., description="Unique engine ID (UUID)")
    engine_name: str = Field(..., description="Engine name")
    engine_version: str = Field(..., description="Engine version")

    # Upload details
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    file_size_kb: float = Field(..., description="Engine file size in KB")
    checksum: str = Field(..., description="SHA256 checksum")

    # Status
    active: bool = Field(..., description="True if this engine is active")
    approved: bool = Field(False, description="True if approved for production use")

    # Validation
    validation_status: str = Field(..., description="Validation status (passed, failed, pending)")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors if any")

    # Metadata
    storage_path: str = Field(..., description="Server-side storage path")
    author: Optional[str] = Field(None, description="Engine author")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class GapAnalysisResponse(BaseModel):
    """
    Response from gap filler analysis

    Flow: ML Server → Admin Frontend
    Shows what data is missing for a model.
    """
    # Model identification
    model_id: str = Field(..., description="Model ID")
    model_name: str = Field(..., description="Model name")
    trained_until_date: str = Field(..., description="Last date in training data (YYYY-MM-DD)")

    # Gap analysis
    target_date: str = Field(..., description="Target date (YYYY-MM-DD)")
    gap_days: int = Field(..., description="Number of days of data gap")
    requires_gap_fill: bool = Field(..., description="True if gap filling is required")

    # Missing data details
    missing_spot_prices: bool = Field(..., description="True if Spot prices missing")
    missing_on_demand_prices: bool = Field(..., description="True if On-Demand prices missing")
    missing_spot_advisor: bool = Field(..., description="True if Spot Advisor data missing")

    # Instance types affected
    instance_types_affected: List[str] = Field(default_factory=list, description="Instance types with gaps")
    regions_affected: List[str] = Field(default_factory=list, description="Regions with gaps")

    # Estimated work
    estimated_fetch_time_minutes: int = Field(0, description="Estimated time to fill gaps (minutes)")
    estimated_data_size_mb: int = Field(0, description="Estimated data size (MB)")


class GapFillResponse(BaseModel):
    """
    Response from gap filler fill operation

    Flow: ML Server → Admin Frontend
    Shows results of gap filling job.
    """
    # Job identification
    job_id: str = Field(..., description="Gap fill job ID (UUID)")
    model_id: str = Field(..., description="Model ID")

    # Job status
    status: str = Field(..., description="Job status (in_progress, completed, failed)")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None, description="Completion time")

    # Progress
    progress_percentage: float = Field(0.0, description="Progress (0.0 to 1.0)")
    records_fetched: int = Field(0, description="Number of records fetched")
    records_processed: int = Field(0, description="Number of records processed")

    # Results
    spot_prices_fetched: int = Field(0, description="Spot price records fetched")
    on_demand_prices_fetched: int = Field(0, description="On-Demand price records fetched")
    spot_advisor_updated: bool = Field(False, description="Spot Advisor data updated")

    # Errors
    errors: List[str] = Field(default_factory=list, description="Errors encountered")

    # Metadata
    duration_seconds: Optional[float] = Field(None, description="Total duration (seconds)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class HealthCheckResponse(BaseModel):
    """
    Health check response

    Flow: Any component → Admin Frontend
    Used for monitoring component health.
    """
    # Service identification
    service: str = Field(..., description="Service name (ml-server, core-platform)")
    version: str = Field(..., description="Service version")

    # Health status
    status: str = Field(..., description="Status (healthy, degraded, unhealthy)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Component health
    database_healthy: bool = Field(..., description="Database connection healthy")
    redis_healthy: bool = Field(..., description="Redis connection healthy")
    ml_server_healthy: Optional[bool] = Field(None, description="ML Server healthy (Core Platform only)")

    # Metrics
    uptime_seconds: float = Field(0.0, description="Service uptime (seconds)")
    request_count: int = Field(0, description="Total requests processed")
    error_count: int = Field(0, description="Total errors encountered")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class OptimizationHistoryResponse(BaseModel):
    """
    Response for optimization history query

    Flow: Core Platform → Admin Frontend
    Shows past optimizations for analytics.
    """
    # Pagination
    total_count: int = Field(..., description="Total number of optimizations")
    page: int = Field(1, description="Current page")
    page_size: int = Field(20, description="Items per page")

    # Optimizations
    optimizations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of optimization records"
    )

    # Aggregated stats
    total_savings_usd: float = Field(0.0, description="Total savings across all optimizations (USD)")
    success_rate: float = Field(0.0, description="Success rate (0.0 to 1.0)")

    # Metadata
    queried_at: datetime = Field(default_factory=datetime.utcnow)
