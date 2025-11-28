"""
Pydantic Schemas for Request/Response Validation

These schemas validate API inputs and outputs, ensuring type safety
and proper data structure across the ML Server API.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal


# ============================================================================
# Model Management Schemas
# ============================================================================

class ModelUploadRequest(BaseModel):
    """Request schema for model upload"""
    model_name: str = Field(..., min_length=1, max_length=255)
    model_version: str = Field(..., min_length=1, max_length=50)
    model_type: str = Field(..., pattern="^(spot_predictor|resource_forecaster)$")
    trained_until_date: date
    uploaded_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ModelResponse(BaseModel):
    """Response schema for model data"""
    model_id: UUID
    model_name: str
    model_version: str
    model_type: str
    trained_until_date: date
    upload_date: datetime
    active: bool
    model_file_path: str
    model_metadata: Optional[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ModelListResponse(BaseModel):
    """Response schema for model list"""
    models: List[ModelResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Decision Engine Schemas
# ============================================================================

class EngineUploadRequest(BaseModel):
    """Request schema for decision engine upload"""
    engine_name: str = Field(..., min_length=1, max_length=255)
    engine_version: str = Field(..., min_length=1, max_length=50)
    engine_type: str = Field(
        ...,
        pattern="^(spot_optimizer|bin_packing|rightsizing|scheduler|ghost_probe|volume_cleanup|network_optimizer|oomkilled_remediation)$"
    )
    config: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class EngineResponse(BaseModel):
    """Response schema for decision engine data"""
    engine_id: UUID
    engine_name: str
    engine_version: str
    engine_type: str
    upload_date: datetime
    active: bool
    config: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# ============================================================================
# Data Gap Filling Schemas
# ============================================================================

class GapAnalysisRequest(BaseModel):
    """Request schema for gap analysis"""
    model_id: UUID
    required_lookback_days: int = Field(default=15, ge=1, le=90)


class GapAnalysisResponse(BaseModel):
    """Response schema for gap analysis"""
    trained_until: date
    current_date: date
    gap_days: int
    required_data_types: List[str]
    estimated_records: int


class GapFillRequest(BaseModel):
    """Request schema for gap filling"""
    model_id: UUID
    instance_types: List[str] = Field(..., min_items=1)
    regions: List[str] = Field(..., min_items=1)
    gap_start_date: date
    gap_end_date: date


class GapFillResponse(BaseModel):
    """Response schema for gap fill trigger"""
    gap_id: UUID
    status: str
    estimated_duration_minutes: int


class GapStatusResponse(BaseModel):
    """Response schema for gap fill status"""
    gap_id: UUID
    status: str
    percent_complete: float
    records_filled: int
    records_expected: int
    eta_seconds: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


# ============================================================================
# Model Refresh Schemas
# ============================================================================

class RefreshTriggerRequest(BaseModel):
    """Request schema for model refresh"""
    model_id: UUID
    refresh_from_date: date
    refresh_to_date: date
    instance_types: List[str] = Field(..., min_items=1)
    regions: List[str] = Field(..., min_items=1)
    auto_activate: bool = False


class RefreshResponse(BaseModel):
    """Response schema for refresh trigger"""
    refresh_id: UUID
    status: str
    estimated_duration_minutes: int


class RefreshStatusResponse(BaseModel):
    """Response schema for refresh status"""
    refresh_id: UUID
    status: str
    percent_complete: float
    records_fetched: int
    started_at: datetime
    eta_seconds: Optional[int] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class RefreshScheduleRequest(BaseModel):
    """Request schema for scheduling automatic refresh"""
    model_id: UUID
    schedule_type: str = Field(..., pattern="^(daily|weekly)$")
    time: str = Field(..., pattern="^([0-1][0-9]|2[0-3]):[0-5][0-9]$")  # HH:MM
    lookback_days: int = Field(default=7, ge=1, le=30)
    enabled: bool = True


# ============================================================================
# Pricing Data Schemas
# ============================================================================

class SpotPriceQuery(BaseModel):
    """Query parameters for Spot price history"""
    instance_type: str
    region: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: int = Field(default=1000, le=10000)


class SpotPriceResponse(BaseModel):
    """Response schema for Spot price data"""
    instance_type: str
    availability_zone: str
    region: str
    spot_price: Decimal
    timestamp: datetime
    product_description: Optional[str] = None


class OnDemandPriceResponse(BaseModel):
    """Response schema for On-Demand price data"""
    instance_type: str
    region: str
    hourly_price: Decimal
    operating_system: Optional[str] = None
    effective_date: date


class SpotAdvisorResponse(BaseModel):
    """Response schema for Spot Advisor data"""
    instance_type: str
    region: str
    interruption_rate: str
    savings_over_od: Optional[int] = None
    last_updated: datetime


class PricingStatsResponse(BaseModel):
    """Response schema for pricing data statistics"""
    spot_prices_count: int
    on_demand_prices_count: int
    spot_advisor_count: int
    last_updated: datetime
    coverage: Dict[str, Any]


# ============================================================================
# Prediction & Decision Schemas
# ============================================================================

class PredictionRequest(BaseModel):
    """Request schema for predictions"""
    instance_type: str
    region: str
    az: str
    spot_price: Decimal
    launch_time: datetime


class PredictionResponse(BaseModel):
    """Response schema for predictions"""
    prediction_id: Optional[int] = None
    interruption_probability: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommendation: str


class DecisionRequest(BaseModel):
    """Request schema for decision engine invocation"""
    request_id: str
    cluster_id: str
    decision_type: str
    current_state: Dict[str, Any]
    requirements: Dict[str, Any]
    constraints: Optional[Dict[str, Any]] = None


class DecisionResponse(BaseModel):
    """Response schema for decision engine output"""
    request_id: str
    decision_type: str
    recommendations: List[Dict[str, Any]]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    estimated_savings: Decimal
    execution_plan: List[Dict[str, Any]]


# ============================================================================
# Health & Metrics Schemas
# ============================================================================

class HealthResponse(BaseModel):
    """Response schema for health check"""
    status: str
    service: str
    version: str
    components: Dict[str, str]


class MetricsResponse(BaseModel):
    """Response schema for system metrics"""
    predictions_per_minute: int
    decisions_per_minute: int
    avg_prediction_latency_ms: float
    cache_hit_rate: float
    database_connections: Dict[str, int]
    uptime_seconds: int
