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
        "version": "1.0.0",
        "status": "running",
        "architecture": "agentless",
        "endpoints": {
            "health": "/api/v1/ml/health",
            "docs": "/api/v1/ml/docs",
            "models": "/api/v1/ml/models/*",
            "engines": "/api/v1/ml/engines/*",
            "gap_filler": "/api/v1/ml/gap-filler/*",
            "refresh": "/api/v1/ml/refresh/*",
            "pricing": "/api/v1/ml/pricing/*",
            "predictions": "/api/v1/ml/predict/*",
            "decisions": "/api/v1/ml/decision/*"
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
# TODO: Uncomment when routers are implemented
# from api.routes import models, engines, predictions, gap_filler, pricing, refresh, health
# app.include_router(models.router, prefix="/api/v1/ml", tags=["Models"])
# app.include_router(engines.router, prefix="/api/v1/ml", tags=["Decision Engines"])
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
