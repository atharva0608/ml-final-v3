"""
Feature Toggle API Routes

Endpoints for managing advanced feature toggles
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to config file
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "ml_config.yaml"

# ============================================================================
# Pydantic Schemas
# ============================================================================

class FeatureConfig(BaseModel):
    """Feature configuration schema"""
    enabled: bool = Field(..., description="Feature enabled state")
    description: str = Field(..., description="Feature description")
    auto_scan_interval_hours: Optional[int] = Field(None, description="Auto-scan interval in hours")
    bloat_threshold_mb: Optional[int] = Field(None, description="Image bloat threshold (MB)")
    min_age_days: Optional[int] = Field(None, description="Minimum resource age in days")
    bandwidth_outlier_multiplier: Optional[int] = Field(None, description="Bandwidth outlier multiplier")

class FeatureToggles(BaseModel):
    """All feature toggles"""
    ipv4_cost_tracking: FeatureConfig
    image_bloat_analysis: FeatureConfig
    shadow_it_detection: FeatureConfig
    noisy_neighbor_detection: FeatureConfig

class FeatureUpdateRequest(BaseModel):
    """Request to update feature toggle"""
    enabled: bool = Field(..., description="New enabled state")

class FeatureUpdateResponse(BaseModel):
    """Response after updating feature"""
    feature_name: str
    enabled: bool
    message: str

# ============================================================================
# Helper Functions
# ============================================================================

def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Failed to load config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load configuration: {str(e)}"
        )

def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to YAML file"""
    try:
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        logger.error(f"Failed to save config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save configuration: {str(e)}"
        )

def get_feature_toggles_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract feature toggles from config"""
    try:
        return config.get("decision_engines", {}).get("feature_toggles", {})
    except Exception as e:
        logger.error(f"Failed to extract feature toggles: {e}", exc_info=True)
        return {}

# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/features/toggles",
    response_model=Dict[str, Any],
    summary="Get All Feature Toggles",
    description="Retrieve current state of all feature toggles"
)
async def get_feature_toggles():
    """
    Get all feature toggle states

    Returns configuration for all 4 advanced features:
    - IPv4 Cost Tracking
    - Image Bloat Analysis
    - Shadow IT Detection
    - Noisy Neighbor Detection
    """
    try:
        config = load_config()
        feature_toggles = get_feature_toggles_from_config(config)

        if not feature_toggles:
            # Return default configuration if not found
            logger.warning("Feature toggles not found in config, returning defaults")
            return {
                "feature_toggles": {
                    "ipv4_cost_tracking": {
                        "enabled": True,
                        "description": "Track IPv4 public IP costs (AWS charges $0.005/hr since Feb 2024)",
                        "auto_scan_interval_hours": 24
                    },
                    "image_bloat_analysis": {
                        "enabled": True,
                        "description": "Analyze container image sizes and calculate bloat tax",
                        "auto_scan_interval_hours": 168,
                        "bloat_threshold_mb": 500
                    },
                    "shadow_it_detection": {
                        "enabled": True,
                        "description": "Detect AWS resources not managed by Kubernetes",
                        "auto_scan_interval_hours": 24,
                        "min_age_days": 7
                    },
                    "noisy_neighbor_detection": {
                        "enabled": True,
                        "description": "Detect pods causing excessive network traffic",
                        "auto_scan_interval_hours": 6,
                        "bandwidth_outlier_multiplier": 10
                    }
                }
            }

        return {
            "feature_toggles": feature_toggles
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get feature toggles: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve feature toggles: {str(e)}"
        )

@router.get(
    "/features/toggles/{feature_name}",
    response_model=FeatureConfig,
    summary="Get Single Feature Toggle",
    description="Retrieve configuration for a specific feature"
)
async def get_feature_toggle(feature_name: str):
    """
    Get configuration for a specific feature

    Parameters:
    - feature_name: One of ipv4_cost_tracking, image_bloat_analysis,
                    shadow_it_detection, noisy_neighbor_detection
    """
    valid_features = [
        "ipv4_cost_tracking",
        "image_bloat_analysis",
        "shadow_it_detection",
        "noisy_neighbor_detection"
    ]

    if feature_name not in valid_features:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature '{feature_name}' not found. Valid features: {', '.join(valid_features)}"
        )

    try:
        config = load_config()
        feature_toggles = get_feature_toggles_from_config(config)

        if feature_name not in feature_toggles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature '{feature_name}' not found in configuration"
            )

        return feature_toggles[feature_name]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get feature toggle: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve feature toggle: {str(e)}"
        )

@router.put(
    "/features/toggles/{feature_name}",
    response_model=FeatureUpdateResponse,
    summary="Update Feature Toggle",
    description="Enable or disable a specific feature"
)
async def update_feature_toggle(feature_name: str, update: FeatureUpdateRequest):
    """
    Update feature toggle state (enable/disable)

    Parameters:
    - feature_name: Feature to update
    - enabled: New enabled state (true/false)

    Returns: Updated feature state
    """
    valid_features = [
        "ipv4_cost_tracking",
        "image_bloat_analysis",
        "shadow_it_detection",
        "noisy_neighbor_detection"
    ]

    if feature_name not in valid_features:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature '{feature_name}' not found. Valid features: {', '.join(valid_features)}"
        )

    try:
        # Load current config
        config = load_config()

        # Update feature toggle
        if "decision_engines" not in config:
            config["decision_engines"] = {}
        if "feature_toggles" not in config["decision_engines"]:
            config["decision_engines"]["feature_toggles"] = {}

        if feature_name not in config["decision_engines"]["feature_toggles"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature '{feature_name}' not found in configuration"
            )

        # Update enabled state
        config["decision_engines"]["feature_toggles"][feature_name]["enabled"] = update.enabled

        # Save config
        save_config(config)

        logger.info(f"Feature '{feature_name}' {'enabled' if update.enabled else 'disabled'}")

        return FeatureUpdateResponse(
            feature_name=feature_name,
            enabled=update.enabled,
            message=f"Feature '{feature_name}' successfully {'enabled' if update.enabled else 'disabled'}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update feature toggle: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update feature toggle: {str(e)}"
        )

@router.post(
    "/features/toggles/{feature_name}/scan",
    summary="Trigger Manual Feature Scan",
    description="Manually trigger a scan for a specific feature"
)
async def trigger_feature_scan(feature_name: str):
    """
    Manually trigger a scan for a specific feature

    This endpoint allows manual execution of a feature scan outside
    of the automatic scanning schedule.

    Parameters:
    - feature_name: Feature to scan

    Returns: Scan execution status
    """
    valid_features = [
        "ipv4_cost_tracking",
        "image_bloat_analysis",
        "shadow_it_detection",
        "noisy_neighbor_detection"
    ]

    if feature_name not in valid_features:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature '{feature_name}' not found"
        )

    try:
        # Check if feature is enabled
        config = load_config()
        feature_toggles = get_feature_toggles_from_config(config)

        if feature_name not in feature_toggles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature '{feature_name}' not found in configuration"
            )

        if not feature_toggles[feature_name].get("enabled", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Feature '{feature_name}' is disabled. Enable it first."
            )

        # TODO: Implement actual scan execution
        # This would typically:
        # 1. Create a background task
        # 2. Execute the decision engine
        # 3. Save results to database
        # 4. Return scan ID for status tracking

        logger.info(f"Manual scan triggered for feature: {feature_name}")

        return {
            "feature_name": feature_name,
            "scan_status": "triggered",
            "message": f"Manual scan for '{feature_name}' has been queued",
            "scan_id": "placeholder-scan-id",  # TODO: Generate real scan ID
            "estimated_completion_seconds": 30
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger feature scan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger feature scan: {str(e)}"
        )

@router.get(
    "/features/stats",
    summary="Get Feature Usage Statistics",
    description="Retrieve usage statistics for all features"
)
async def get_feature_stats():
    """
    Get usage statistics for all features

    Returns metrics like:
    - Total scans executed
    - Total savings found
    - Last scan time
    - Average execution time
    """
    # TODO: Implement actual stats from database
    # This is placeholder data

    return {
        "ipv4_cost_tracking": {
            "total_scans": 0,
            "total_findings": 0,
            "total_monthly_savings": 0.0,
            "last_scan_time": None,
            "avg_execution_time_ms": 0
        },
        "image_bloat_analysis": {
            "total_scans": 0,
            "total_findings": 0,
            "total_monthly_savings": 0.0,
            "last_scan_time": None,
            "avg_execution_time_ms": 0
        },
        "shadow_it_detection": {
            "total_scans": 0,
            "total_findings": 0,
            "total_monthly_savings": 0.0,
            "last_scan_time": None,
            "avg_execution_time_ms": 0
        },
        "noisy_neighbor_detection": {
            "total_scans": 0,
            "total_findings": 0,
            "total_monthly_savings": 0.0,
            "last_scan_time": None,
            "avg_execution_time_ms": 0
        },
        "overall": {
            "total_monthly_savings": 0.0,
            "total_annual_savings": 0.0,
            "total_findings": 0
        }
    }
