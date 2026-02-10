"""Health check endpoints"""

from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    timestamp: datetime
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    
    Returns the current health status of the service
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        service="Sentinel AI Policy Engine",
        version="0.1.0"
    )


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness check endpoint
    
    Returns whether the service is ready to accept requests
    """
    # TODO: Add database connectivity check
    # TODO: Add cache connectivity check
    return {
        "ready": True,
        "timestamp": datetime.utcnow()
    }


@router.get("/health/live")
async def liveness_check():
    """
    Liveness check endpoint
    
    Returns whether the service is alive
    """
    return {
        "alive": True,
        "timestamp": datetime.utcnow()
    }
