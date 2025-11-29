"""
Core Platform - Main FastAPI Application

Purpose: Central control plane for agentless Kubernetes cost optimization
Architecture: EventBridge + SQS + Remote Kubernetes API (NO agents)
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

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for Core Platform
    - Startup: Initialize database, start SQS poller, connect to ML Server
    - Shutdown: Cleanup connections, stop background tasks
    """
    logger.info("=" * 60)
    logger.info("Core Platform Starting...")
    logger.info("=" * 60)

    # Startup tasks
    logger.info("✓ Initializing database connection...")
    # TODO: Initialize PostgreSQL connection pool

    logger.info("✓ Connecting to Redis cache...")
    # TODO: Initialize Redis connection

    logger.info("✓ Testing ML Server connectivity...")
    # TODO: Test connection to ML Server API

    logger.info("✓ Starting SQS poller for Spot warnings...")
    # TODO: Start EventBridge/SQS polling service

    logger.info("✓ Initializing remote Kubernetes API clients...")
    # TODO: Initialize K8s clients for registered clusters

    logger.info("=" * 60)
    logger.info("Core Platform Ready!")
    logger.info("Backend API: http://0.0.0.0:8000/api/v1/")
    logger.info("Admin Frontend: http://0.0.0.0:80")
    logger.info("Health Check: http://0.0.0.0:8000/health")
    logger.info("=" * 60)

    yield

    # Shutdown tasks
    logger.info("Core Platform shutting down...")
    logger.info("✓ Stopping SQS poller...")
    # TODO: Stop background polling tasks

    logger.info("✓ Closing database connections...")
    # TODO: Close database pool

    logger.info("Core Platform stopped.")


# Create FastAPI application
app = FastAPI(
    title="Core Platform - CloudOptim",
    description="Central control plane for agentless Kubernetes cost optimization (CAST AI competitor)",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
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
        "service": "Core Platform",
        "version": "1.0.0",
        "architecture": "agentless",
        "description": "Central control plane for Kubernetes cost optimization",
        "endpoints": {
            "health": "/health",
            "docs": "/api/v1/docs",
            "clusters": "/api/v1/admin/clusters",
            "optimization": "/api/v1/optimization/*",
            "events": "/api/v1/events/*",
            "k8s_remote": "/api/v1/k8s/*"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint
    Returns: System health status
    """
    return {
        "status": "healthy",
        "service": "core-platform",
        "version": "1.0.0",
        "components": {
            "database": "up",  # TODO: Check database
            "redis": "up",     # TODO: Check Redis
            "ml_server": "up",  # TODO: Check ML Server connectivity
            "sqs_poller": "running"  # TODO: Check SQS poller status
        }
    }

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """System metrics endpoint"""
    return {
        "clusters_monitored": 0,
        "spot_warnings_processed_today": 0,
        "optimizations_executed_today": 0,
        "total_monthly_savings": 0.0,
        "sqs_poll_rate_per_second": 0.2,  # Every 5 seconds
        "avg_k8s_api_latency_ms": 0
    }

# Import and register routers
# TODO: Uncomment when routers are implemented
# from api.routes import customers, clusters, optimization, ml_proxy, events, admin
# app.include_router(customers.router, prefix="/api/v1", tags=["Customers"])
# app.include_router(clusters.router, prefix="/api/v1/admin", tags=["Clusters"])
# app.include_router(optimization.router, prefix="/api/v1/optimization", tags=["Optimization"])
# app.include_router(ml_proxy.router, prefix="/api/v1/ml", tags=["ML Proxy"])
# app.include_router(events.router, prefix="/api/v1/events", tags=["Events"])
# app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Disable in production
        workers=1,    # Use 4+ workers in production
        log_level="info"
    )
