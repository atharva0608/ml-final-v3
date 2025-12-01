"""
CloudOptim ML Server - Customer Feedback API
============================================

Purpose: Ingest real interruption data from Core Platform to enable ML learning
Author: Architecture Team
Date: 2025-12-01

Customer Feedback Loop Flow:
1. Core Platform detects Spot interruption
2. Core Platform sends interruption data to this API
3. FeedbackLearningService ingests and processes data
4. Risk scores updated in risk_score_adjustments table
5. Customer feedback weight grows from 0% → 25% over time

This API is the KEY to building competitive moat:
- Month 1: 0% customer weight (AWS Spot Advisor only)
- Month 6: 15% customer weight (patterns emerging)
- Month 12: 25% customer weight (insurmountable advantage)

Endpoints:
- POST /api/v1/ml/feedback/interruption - Ingest interruption event
- GET /api/v1/ml/feedback/patterns/{instance_type} - Get learned patterns
- GET /api/v1/ml/feedback/stats - Get learning statistics
- GET /api/v1/ml/feedback/weight - Get current feedback weight

Integration:
- Core Platform calls /interruption after every Spot interruption
- ML Server updates risk_score_adjustments table
- Updated risk scores used in next Spot optimization decision
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from ...database.session import get_db
from ...services.feedback_service import FeedbackLearningService

router = APIRouter(prefix="/api/v1/ml/feedback", tags=["feedback"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class InterruptionFeedbackRequest(BaseModel):
    """
    Interruption feedback data from Core Platform

    This schema matches the interruption_feedback table in Core Platform database.
    Core Platform sends this data after every Spot interruption.
    """
    # Cluster identification
    cluster_id: UUID
    customer_id: UUID

    # Instance details
    instance_id: str = Field(..., description="EC2 instance ID")
    instance_type: str = Field(..., description="EC2 instance type (e.g., m5.large)")
    availability_zone: str = Field(..., description="Availability zone (e.g., us-east-1a)")
    region: str = Field(..., description="AWS region (e.g., us-east-1)")

    # Workload classification
    workload_type: Optional[str] = Field(None, description="Workload type: web, database, ml, batch, etc.")
    pod_name: Optional[str] = Field(None, description="Kubernetes pod name")
    namespace: Optional[str] = Field(None, description="Kubernetes namespace")

    # Timing data
    interruption_time: datetime = Field(..., description="When interruption occurred")

    # ML prediction tracking
    was_predicted: bool = Field(default=False, description="Did ML model predict this interruption?")
    risk_score_at_deployment: Optional[Decimal] = Field(None, ge=0, le=1, description="Risk score when deployed")

    # Recovery metrics
    drain_started_at: Optional[datetime] = None
    drain_completed_at: Optional[datetime] = None
    replacement_ready_at: Optional[datetime] = None
    total_recovery_seconds: Optional[int] = Field(None, ge=0, description="Total recovery time in seconds")

    # Impact assessment
    customer_impact: Optional[str] = Field(None, description="Impact: none, minimal, moderate, severe")
    workload_disrupted: bool = Field(default=False)
    data_loss_occurred: bool = Field(default=False)

    @validator('customer_impact')
    def validate_customer_impact(cls, v):
        if v and v not in ['none', 'minimal', 'moderate', 'severe']:
            raise ValueError("customer_impact must be: none, minimal, moderate, or severe")
        return v

    class Config:
        schema_extra = {
            "example": {
                "cluster_id": "123e4567-e89b-12d3-a456-426614174000",
                "customer_id": "987fcdeb-51a2-43c1-9012-345678901234",
                "instance_id": "i-1234567890abcdef0",
                "instance_type": "m5.large",
                "availability_zone": "us-east-1a",
                "region": "us-east-1",
                "workload_type": "web",
                "pod_name": "nginx-deployment-7d8f9c5b6-xh2jk",
                "namespace": "production",
                "interruption_time": "2025-12-01T14:32:15Z",
                "was_predicted": False,
                "risk_score_at_deployment": 0.85,
                "drain_started_at": "2025-12-01T14:32:15Z",
                "drain_completed_at": "2025-12-01T14:33:45Z",
                "replacement_ready_at": "2025-12-01T14:35:20Z",
                "total_recovery_seconds": 185,
                "customer_impact": "minimal",
                "workload_disrupted": False,
                "data_loss_occurred": False
            }
        }


class InterruptionFeedbackResponse(BaseModel):
    """Response after ingesting interruption feedback"""
    success: bool
    message: str
    risk_adjustment_updated: bool
    new_risk_score: Optional[Decimal] = None
    confidence: Optional[Decimal] = None
    data_points_count: int
    feedback_weight: Decimal = Field(..., description="Current customer feedback weight (0.0-0.25)")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Interruption feedback ingested successfully",
                "risk_adjustment_updated": True,
                "new_risk_score": 0.82,
                "confidence": 0.65,
                "data_points_count": 327,
                "feedback_weight": 0.15
            }
        }


class PatternResponse(BaseModel):
    """Learned patterns for an instance type"""
    instance_type: str
    availability_zone: str
    region: str

    base_score: Decimal
    customer_adjustment: Decimal
    final_score: Decimal
    confidence: Decimal

    temporal_patterns: Optional[Dict[str, Any]] = None
    workload_patterns: Optional[Dict[str, Any]] = None
    seasonal_patterns: Optional[Dict[str, Any]] = None

    data_points_count: int
    interruption_count: int
    actual_interruption_rate: Optional[Decimal] = None

    last_updated: datetime


class LearningStatsResponse(BaseModel):
    """Global learning statistics"""
    total_interruptions: int
    total_instance_hours: int
    total_unique_pools: int

    pools_with_data: int
    pools_with_confidence: int
    pools_with_temporal_patterns: int
    pools_with_workload_patterns: int

    current_feedback_weight: Decimal = Field(..., ge=0, le=0.25)
    target_feedback_weight: Decimal = Field(default=Decimal('0.25'))

    overall_prediction_accuracy: Optional[Decimal] = None
    high_confidence_accuracy: Optional[Decimal] = None

    learning_stage: str = Field(..., description="month_1, month_3, month_6, month_12, mature")

    class Config:
        schema_extra = {
            "example": {
                "total_interruptions": 1247,
                "total_instance_hours": 125430,
                "total_unique_pools": 42,
                "pools_with_data": 42,
                "pools_with_confidence": 28,
                "pools_with_temporal_patterns": 15,
                "pools_with_workload_patterns": 12,
                "current_feedback_weight": 0.12,
                "target_feedback_weight": 0.25,
                "overall_prediction_accuracy": 0.87,
                "high_confidence_accuracy": 0.92,
                "learning_stage": "month_6"
            }
        }


class FeedbackWeightResponse(BaseModel):
    """Current customer feedback weight"""
    current_weight: Decimal = Field(..., ge=0, le=0.25)
    target_weight: Decimal = Field(default=Decimal('0.25'))
    progress_percentage: Decimal = Field(..., ge=0, le=100)
    learning_stage: str
    total_instance_hours: int

    milestones: Dict[str, Any] = Field(
        default={
            "month_1": {"instance_hours": 10000, "weight": 0.00},
            "month_3": {"instance_hours": 50000, "weight": 0.10},
            "month_6": {"instance_hours": 200000, "weight": 0.15},
            "month_12": {"instance_hours": 500000, "weight": 0.25}
        }
    )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post(
    "/interruption",
    response_model=InterruptionFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest Spot interruption feedback",
    description=(
        "Ingest interruption data from Core Platform to enable ML learning. "
        "This endpoint is called by Core Platform after every Spot interruption. "
        "Data is used to update risk_score_adjustments table and grow customer feedback weight."
    )
)
async def ingest_interruption_feedback(
    feedback: InterruptionFeedbackRequest,
    db: AsyncSession = Depends(get_db)
) -> InterruptionFeedbackResponse:
    """
    Ingest interruption feedback from Core Platform

    Flow:
    1. Validate interruption data
    2. Store in feedback learning system
    3. Update risk_score_adjustments table
    4. Update temporal/workload patterns
    5. Recalculate customer feedback weight
    6. Return updated risk score and confidence

    This is the PRIMARY data ingestion point for ML learning.
    """
    try:
        feedback_service = FeedbackLearningService(db)

        # Ingest interruption data
        result = await feedback_service.ingest_interruption(
            interruption_data=feedback.dict()
        )

        return InterruptionFeedbackResponse(
            success=result['success'],
            message=result.get('message', 'Interruption feedback ingested successfully'),
            risk_adjustment_updated=result.get('risk_adjustment_updated', False),
            new_risk_score=result.get('new_risk_score'),
            confidence=result.get('confidence'),
            data_points_count=result.get('data_points_count', 0),
            feedback_weight=result.get('feedback_weight', Decimal('0.0'))
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest interruption feedback: {str(e)}"
        )


@router.get(
    "/patterns/{instance_type}",
    response_model=List[PatternResponse],
    summary="Get learned patterns for instance type",
    description=(
        "Get all learned patterns (temporal, workload, seasonal) for a specific instance type. "
        "This shows how ML has learned from real interruptions."
    )
)
async def get_learned_patterns(
    instance_type: str,
    region: Optional[str] = None,
    availability_zone: Optional[str] = None,
    min_confidence: Optional[float] = 0.0,
    db: AsyncSession = Depends(get_db)
) -> List[PatternResponse]:
    """
    Get learned patterns for instance type

    Returns all risk_score_adjustments records for the specified instance type,
    optionally filtered by region, AZ, and minimum confidence.
    """
    try:
        feedback_service = FeedbackLearningService(db)

        patterns = await feedback_service.get_patterns(
            instance_type=instance_type,
            region=region,
            availability_zone=availability_zone,
            min_confidence=min_confidence
        )

        return [PatternResponse(**pattern) for pattern in patterns]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get patterns: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=LearningStatsResponse,
    summary="Get global learning statistics",
    description=(
        "Get high-level statistics about ML learning progress across all customers. "
        "Shows total interruptions, instance-hours, feedback weight, and prediction accuracy."
    )
)
async def get_learning_statistics(
    db: AsyncSession = Depends(get_db)
) -> LearningStatsResponse:
    """
    Get global learning statistics

    Returns:
    - Total interruptions observed
    - Total instance-hours (competitive moat indicator)
    - Current customer feedback weight (0% → 25%)
    - Prediction accuracy metrics
    - Learning stage (month_1, month_3, month_6, month_12, mature)
    """
    try:
        feedback_service = FeedbackLearningService(db)

        stats = await feedback_service.get_learning_stats()

        return LearningStatsResponse(**stats)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get learning statistics: {str(e)}"
        )


@router.get(
    "/weight",
    response_model=FeedbackWeightResponse,
    summary="Get current customer feedback weight",
    description=(
        "Get current customer feedback weight in risk scoring formula. "
        "Weight grows from 0% (Month 1) to 25% (Month 12+) based on data maturity."
    )
)
async def get_feedback_weight(
    db: AsyncSession = Depends(get_db)
) -> FeedbackWeightResponse:
    """
    Get current customer feedback weight

    The customer feedback weight determines how much ML learning influences
    risk scores vs AWS Spot Advisor static data.

    Weight growth:
    - Month 1 (0-10K instance-hours): 0%
    - Month 3 (10K-50K): 0% → 10%
    - Month 6 (50K-200K): 10% → 15%
    - Month 12 (200K-500K): 15% → 25%
    - Mature (500K+): 25% (competitive moat)
    """
    try:
        feedback_service = FeedbackLearningService(db)

        weight_info = await feedback_service.get_feedback_weight_info()

        return FeedbackWeightResponse(**weight_info)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback weight: {str(e)}"
        )


@router.delete(
    "/patterns/{instance_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset learned patterns (admin only)",
    description=(
        "Reset learned patterns for an instance type. "
        "USE WITH CAUTION - This deletes ML learning data."
    )
)
async def reset_patterns(
    instance_type: str,
    region: Optional[str] = None,
    availability_zone: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset learned patterns (admin endpoint)

    Deletes risk_score_adjustments records for the specified instance type.
    This should only be used for testing or if corrupted data is detected.
    """
    try:
        feedback_service = FeedbackLearningService(db)

        await feedback_service.reset_patterns(
            instance_type=instance_type,
            region=region,
            availability_zone=availability_zone
        )

        return None

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset patterns: {str(e)}"
        )


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get(
    "/health",
    summary="Feedback API health check",
    description="Check if feedback API is operational"
)
async def feedback_health_check(db: AsyncSession = Depends(get_db)):
    """Health check for feedback API"""
    try:
        feedback_service = FeedbackLearningService(db)

        # Quick database connectivity check
        stats = await feedback_service.get_learning_stats()

        return {
            "status": "healthy",
            "service": "feedback_api",
            "total_interruptions": stats['total_interruptions'],
            "current_feedback_weight": float(stats['current_feedback_weight']),
            "learning_stage": stats['learning_stage']
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Feedback API unhealthy: {str(e)}"
        )
