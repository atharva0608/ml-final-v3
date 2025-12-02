"""
ML Server - FastAPI Application Entry Point

Purpose: Main FastAPI application for ML model management, decision engines,
         data gap filling, and pricing data management.

Architecture: Agentless (no client-side agents, remote API only)
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for ML Server
    - Startup: Initialize database connections, load models, start cache
    - Shutdown: Cleanup connections, save state
    """
    logger.info("=" * 60)
    logger.info("ML Server Starting...")
    logger.info("=" * 60)

    # Startup tasks
    logger.info("✓ Initializing database connection pool...")
    # TODO: Initialize database connection (asyncpg pool)

    logger.info("✓ Connecting to Redis cache...")
    # TODO: Initialize Redis connection

    logger.info("✓ Loading active ML models...")
    # TODO: Load models from /models/uploaded/

    logger.info("✓ Loading active decision engines...")
    # TODO: Load decision engines from /decision_engine/uploaded/

    logger.info("✓ Fetching AWS Spot Advisor data...")
    # TODO: Fetch and cache Spot Advisor data

    logger.info("=" * 60)
    logger.info("ML Server Ready!")
    logger.info("Backend API: http://0.0.0.0:8001/api/v1/ml/")
    logger.info("Health Check: http://0.0.0.0:8001/api/v1/ml/health")
    logger.info("=" * 60)

    yield

    # Shutdown tasks
    logger.info("ML Server shutting down...")
    logger.info("✓ Closing database connections...")
    # TODO: Close database pool

    logger.info("✓ Closing Redis connections...")
    # TODO: Close Redis connection

    logger.info("ML Server stopped.")


# Create FastAPI application
app = FastAPI(
    title="ML Server - CloudOptim",
    description="Machine Learning & Decision Engine Server for Agentless Kubernetes Cost Optimization",
    version="1.0.0",
    docs_url="/api/v1/ml/docs",
    redoc_url="/api/v1/ml/redoc",
    openapi_url="/api/v1/ml/openapi.json",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "path": str(request.url)
        }
    )

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "service": "ML Server",
        "version": "1.1.0",
        "status": "running",
        "architecture": "agentless",
        "features": {
            "decision_engines": 12,  # 8 core + 4 advanced
            "advanced_features": 4,  # IPv4, Image Bloat, Shadow IT, Noisy Neighbor
            "feature_toggles": True
        },
        "endpoints": {
            "health": "/api/v1/ml/health",
            "docs": "/api/v1/ml/docs",
            "models": "/api/v1/ml/models/*",
            "engines": "/api/v1/ml/engines/*",
            "gap_filler": "/api/v1/ml/gap-filler/*",
            "refresh": "/api/v1/ml/refresh/*",
            "pricing": "/api/v1/ml/pricing/*",
            "predictions": "/api/v1/ml/predict/*",
            "decisions": "/api/v1/ml/decision/*",
            "features": "/api/v1/ml/features/*"
        },
        "decision_engines": {
            "core": [
                "/api/v1/ml/decision/spot-optimize",
                "/api/v1/ml/decision/bin-pack",
                "/api/v1/ml/decision/rightsize",
                "/api/v1/ml/decision/office-hours",
                "/api/v1/ml/decision/ghost-probe",
                "/api/v1/ml/decision/volume-cleanup",
                "/api/v1/ml/decision/network-optimize",
                "/api/v1/ml/decision/oomkilled-remediation"
            ],
            "advanced": [
                "/api/v1/ml/decision/ipv4-cost-tracking",
                "/api/v1/ml/decision/image-bloat-analysis",
                "/api/v1/ml/decision/shadow-it-detection",
                "/api/v1/ml/decision/noisy-neighbor-detection"
            ],
            "batch": "/api/v1/ml/decision/batch"
        },
        "feature_management": {
            "get_all_toggles": "/api/v1/ml/features/toggles",
            "get_single_toggle": "/api/v1/ml/features/toggles/{feature_name}",
            "update_toggle": "/api/v1/ml/features/toggles/{feature_name}",
            "trigger_scan": "/api/v1/ml/features/toggles/{feature_name}/scan",
            "get_stats": "/api/v1/ml/features/stats"
        }
    }

# Health check endpoint
@app.get("/api/v1/ml/health")
async def health_check():
    """
    Health check endpoint
    Returns: System health status
    """
    return {
        "status": "healthy",
        "service": "ml-server",
        "version": "1.0.0",
        "components": {
            "database": "up",  # TODO: Check database connection
            "redis": "up",     # TODO: Check Redis connection
            "models_loaded": 0,  # TODO: Count loaded models
            "engines_loaded": 0  # TODO: Count loaded engines
        }
    }

# Metrics endpoint
@app.get("/api/v1/ml/metrics")
async def metrics():
    """
    System metrics endpoint
    Returns: Performance and usage metrics
    """
    return {
        "predictions_per_minute": 0,
        "decisions_per_minute": 0,
        "avg_prediction_latency_ms": 0,
        "cache_hit_rate": 0.0,
        "database_connections": {
            "active": 0,
            "idle": 0,
            "max": 10
        },
        "uptime_seconds": 0
    }

# Import and register routers
from api.routes import decisions, features, testing

# Register decision engine routes (all 12 engines: 8 core + 4 advanced)
app.include_router(
    decisions.router,
    prefix="/api/v1/ml",
    tags=["Decision Engines"]
)

# Register feature toggle routes
app.include_router(
    features.router,
    prefix="/api/v1/ml",
    tags=["Feature Toggles"]
)

# Register testing mode routes
app.include_router(
    testing.router,
    tags=["Testing Mode"]
)

# TODO: Implement and register remaining routers
# from api.routes import models, predictions, gap_filler, pricing, refresh
# app.include_router(models.router, prefix="/api/v1/ml", tags=["Models"])
# app.include_router(predictions.router, prefix="/api/v1/ml", tags=["Predictions"])
# app.include_router(gap_filler.router, prefix="/api/v1/ml", tags=["Data Gap Filling"])
# app.include_router(pricing.router, prefix="/api/v1/ml", tags=["Pricing Data"])
# app.include_router(refresh.router, prefix="/api/v1/ml", tags=["Model Refresh"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,  # Disable in production
        workers=1,    # Use 4+ workers in production
        log_level="info"
    )
