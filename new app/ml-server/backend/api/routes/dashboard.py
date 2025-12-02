"""
Dashboard API Routes

Endpoints for dashboard overview and statistics
"""

from fastapi import APIRouter
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ml/dashboard/stats")
async def get_dashboard_stats():
    """
    Get dashboard overview statistics
    
    Returns:
        Dashboard statistics including savings, predictions, and health metrics
    """
    logger.info("Fetching dashboard statistics")
    
    return {
        "status": "success",
        "stats": {
            "totalSavings": 4520.50,
            "activeModels": 2,
            "predictionsToday": 17892,
            "clusterHealth": 98,
            "activeEngines": 5,
            "costTrend": [4200, 4350, 4100, 4400, 4520.50],
            "alerts": [
                {
                    "type": "warning",
                    "title": "Noisy Neighbor Detected",
                    "message": "Pod 'data-proc-7x' is consuming excessive CPU.",
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "type": "info",
                    "title": "Model Retraining",
                    "message": "SpotPredictor v1.0.5 is currently training.",
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "metrics": {
                "cpu_utilization": 65.4,
                "memory_utilization": 72.1,
                "network_throughput": "1.2 GB/s",
                "active_pods": 156
            }
        },
        "generated_at": datetime.now().isoformat()
    }


@router.get("/ml/dashboard/recent-activity")
async def get_recent_activity():
    """
    Get recent activity log for dashboard
    
    Returns:
        Recent system activities
    """
    logger.info("Fetching recent activity")
    
    return {
        "status": "success",
        "activities": [
            {
                "type": "optimization",
                "action": "Spot Optimizer executed",
                "result": "Saved $45 in last hour",
                "timestamp": datetime.now().isoformat()
            },
            {
                "type": "remediation",
                "action": "OOMKilled pod restarted",
                "result": "Pod 'backend-api-3' limits adjusted",
                "timestamp": datetime.now().isoformat()
            }
        ]
    }
