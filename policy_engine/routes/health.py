"""Health check endpoints.

/health       — liveness (always 200)
/health/live  — liveness (always 200)
/health/ready — readiness: real SELECT 1 + Redis ping; 503 on failure
"""

from typing import Dict, Any

import redis as redis_lib
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

from policy_engine.config import settings
from policy_engine.database import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    service: str
    version: str


class ReadinessChecks(BaseModel):
    database: Dict[str, Any]
    redis: Dict[str, Any]


class ReadinessResponse(BaseModel):
    ready: bool
    timestamp: datetime
    checks: ReadinessChecks


# ---------------------------------------------------------------------------
# Redis dependency (thin wrapper so tests can override it)
# ---------------------------------------------------------------------------

def get_redis_health_client() -> redis_lib.Redis:
    """Return a Redis client used only for the health probe."""
    return redis_lib.from_url(settings.REDIS_URL, socket_timeout=2)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness — always 200."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        service="Sentinel AI Policy Engine",
        version="0.1.0",
    )


@router.get("/health/live")
async def liveness_check():
    """Liveness — always 200."""
    return {"alive": True, "timestamp": datetime.utcnow()}


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(
    response: Response,
    db: Session = Depends(get_db),
    redis_client: redis_lib.Redis = Depends(get_redis_health_client),
):
    """
    Readiness probe — returns 200 only when both DB and Redis are reachable.

    Response body always includes per-dependency check results so that
    monitoring systems can identify which dependency is unhealthy.
    The HTTP status code is set to 503 if any dependency fails; the body
    is still returned so callers can read `checks` for diagnostics.

    Connection strings are never included in the response body to prevent
    credential leakage.
    """
    checks: Dict[str, Dict[str, Any]] = {}
    ready = True

    # -- Database --
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as exc:  # pragma: no cover — covered by broken_db fixture
        checks["database"] = {"status": "error", "detail": type(exc).__name__}
        ready = False

    # -- Redis --
    try:
        redis_client.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as exc:
        checks["redis"] = {"status": "error", "detail": type(exc).__name__}
        ready = False

    if not ready:
        response.status_code = 503

    return ReadinessResponse(
        ready=ready,
        timestamp=datetime.utcnow(),
        checks=ReadinessChecks(**checks),
    )
