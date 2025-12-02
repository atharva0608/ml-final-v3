"""
Decision Engines API Routes

Endpoints for managing and controlling decision engines
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class EngineUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    config: Optional[dict] = None


# Mock decision engines data
engines_data = {
    "eng_spot": {
        "id": "eng_spot",
        "name": "Spot Optimizer",
        "type": "optimization",
        "status": "active",
        "lastRun": "2m ago",
        "impact": "-$450/day",
        "description": "Replaces on-demand instances with spot instances based on price prediction.",
        "enabled": True
    },
    "eng_bin": {
        "id": "eng_bin",
        "name": "Bin Packing",
        "type": "optimization",
        "status": "active",
        "lastRun": "15m ago",
        "impact": "+20% util",
        "description": "Consolidates pods to fewer nodes to reduce cluster footprint.",
        "enabled": True
    },
    "eng_ghost": {
        "id": "eng_ghost",
        "name": "Ghost Probe",
        "type": "analysis",
        "status": "paused",
        "lastRun": "1h ago",
        "impact": "N/A",
        "description": "Detects idle resources and zombie processes.",
        "enabled": False
    },
    "eng_bloat": {
        "id": "eng_bloat",
        "name": "Image Bloat Analyzer",
        "type": "analysis",
        "status": "active",
        "lastRun": "4h ago",
        "impact": "3GB saved",
        "description": "Identifies unused layers in container images.",
        "enabled": True
    },
    "eng_net": {
        "id": "eng_net",
        "name": "Network Optimizer",
        "type": "optimization",
        "status": "active",
        "lastRun": "30m ago",
        "impact": "-$120/day",
        "description": "Optimizes cross-zone data transfer costs.",
        "enabled": True
    },
    "eng_oom": {
        "id": "eng_oom",
        "name": "OOMKilled Remediation",
        "type": "remediation",
        "status": "active",
        "lastRun": "Live",
        "impact": "99.9% uptime",
        "description": "Automatically adjusts limits for OOMKilled pods.",
        "enabled": True
    },
    "eng_noisy": {
        "id": "eng_noisy",
        "name": "Noisy Neighbor Detector",
        "type": "remediation",
        "status": "degraded",
        "lastRun": "5m ago",
        "impact": "Low Conf",
        "description": "Identifies pods stealing CPU cycles from others.",
        "enabled": True
    }
}


@router.get("/decision-engines")
async def list_decision_engines():
    """
    List all decision engines
    
    Returns:
        List of all available decision engines with their status
    """
    logger.info("Fetching all decision engines")
    
    return {
        "status": "success",
        "engines": list(engines_data.values()),
        "total": len(engines_data),
        "active_count": sum(1 for e in engines_data.values() if e["status"] == "active")
    }


@router.get("/decision-engines/{engine_id}")
async def get_decision_engine(engine_id: str):
    """
    Get details of a specific decision engine
    
    Args:
        engine_id: Engine ID
        
    Returns:
        Engine details
    """
    logger.info(f"Fetching decision engine {engine_id}")
    
    if engine_id not in engines_data:
        raise HTTPException(status_code=404, detail="Engine not found")
    
    return {
        "status": "success",
        "engine": engines_data[engine_id]
    }


@router.patch("/decision-engines/{engine_id}")
async def update_decision_engine(engine_id: str, request: EngineUpdateRequest):
    """
    Update decision engine configuration
    
    Args:
        engine_id: Engine ID
        request: Update request with enabled status or config
        
    Returns:
        Updated engine details
    """
    logger.info(f"Updating decision engine {engine_id}")
    
    if engine_id not in engines_data:
        raise HTTPException(status_code=404, detail="Engine not found")
    
    engine = engines_data[engine_id]
    
    if request.enabled is not None:
        engine["enabled"] = request.enabled
        engine["status"] = "active" if request.enabled else "paused"
        logger.info(f"Engine {engine_id} {'enabled' if request.enabled else 'disabled'}")
    
    if request.config is not None:
        # Update configuration
        logger.info(f"Updating config for engine {engine_id}")
    
    return {
        "status": "success",
        "message": "Engine updated successfully",
        "engine": engine
    }


@router.post("/decision-engines/{engine_id}/execute")
async def execute_decision_engine(engine_id: str):
    """
    Manually trigger a decision engine execution
    
    Args:
        engine_id: Engine ID
        
    Returns:
        Execution status
    """
    logger.info(f"Executing decision engine {engine_id}")
    
    if engine_id not in engines_data:
        raise HTTPException(status_code=404, detail="Engine not found")
    
    engine = engines_data[engine_id]
    
    if not engine["enabled"]:
        raise HTTPException(status_code=400, detail="Engine is disabled")
    
    return {
        "status": "success",
        "message": "Engine execution triggered",
        "engine_id": engine_id,
        "triggered_at": datetime.now().isoformat()
    }


@router.get("/decision-engines/stats/summary")
async def get_engines_summary():
    """
    Get summary statistics for all decision engines
    
    Returns:
        Summary stats
    """
    logger.info("Fetching decision engines summary")
    
    return {
        "status": "success",
        "summary": {
            "total_engines": len(engines_data),
            "active": sum(1 for e in engines_data.values() if e["status"] == "active"),
            "paused": sum(1 for e in engines_data.values() if e["status"] == "paused"),
            "degraded": sum(1 for e in engines_data.values() if e["status"] == "degraded"),
            "total_savings": "$570/day",
            "last_updated": datetime.now().isoformat()
        }
    }
