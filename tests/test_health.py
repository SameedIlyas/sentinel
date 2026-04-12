"""Tests for health check endpoints — Task 1.1 (Phase 1).

RED phase: these tests define the expected behaviour of the real readiness
probe.  They will FAIL until health.py is updated to perform live DB and Redis
checks.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from policy_engine.database import get_db
from policy_engine.main import app
from tests.conftest import TestingSessionLocal, _override_get_db


# ---------------------------------------------------------------------------
# Liveness — must always return 200 regardless of dependencies
# ---------------------------------------------------------------------------

def test_health_live_always_200(client):
    """GET /health/live returns 200 and alive=true unconditionally."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["alive"] is True


# ---------------------------------------------------------------------------
# Basic health — must always return 200
# ---------------------------------------------------------------------------

def test_health_returns_200_and_healthy(client):
    """GET /health returns 200 with status='healthy'."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# Readiness — healthy DB + Redis → 200 with checks body
# ---------------------------------------------------------------------------

def _make_healthy_redis() -> MagicMock:
    redis = MagicMock()
    redis.ping.return_value = True
    return redis


def test_health_ready_200_when_all_healthy(_db_tables):
    """GET /health/ready returns 200 when DB and Redis both respond."""
    from policy_engine.routes.health import get_redis_health_client  # noqa: PLC0415

    healthy_redis = _make_healthy_redis()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_health_client] = lambda: healthy_redis

    with TestClient(app, raise_server_exceptions=True) as c:
        response = c.get("/health/ready")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True


def test_health_ready_body_contains_db_and_redis_checks(_db_tables):
    """Readiness response body must include checks.database and checks.redis."""
    from policy_engine.routes.health import get_redis_health_client  # noqa: PLC0415

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_health_client] = lambda: _make_healthy_redis()

    with TestClient(app, raise_server_exceptions=True) as c:
        response = c.get("/health/ready")

    app.dependency_overrides.clear()

    body = response.json()
    assert "checks" in body, "Response must contain 'checks' key"
    checks = body["checks"]
    assert "database" in checks, "checks must include 'database'"
    assert "redis" in checks, "checks must include 'redis'"


# ---------------------------------------------------------------------------
# Readiness — broken DB → 503
# ---------------------------------------------------------------------------

def test_health_ready_503_when_db_down(_db_tables):
    """GET /health/ready returns 503 and ready=false when DB execute fails."""
    from policy_engine.routes.health import get_redis_health_client  # noqa: PLC0415

    def broken_db():
        db = MagicMock()
        db.execute.side_effect = Exception("connection refused")
        yield db

    app.dependency_overrides[get_db] = broken_db
    app.dependency_overrides[get_redis_health_client] = lambda: _make_healthy_redis()

    with TestClient(app, raise_server_exceptions=True) as c:
        response = c.get("/health/ready")

    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["ready"] is False


# ---------------------------------------------------------------------------
# Readiness — broken Redis → 503
# ---------------------------------------------------------------------------

def test_health_ready_503_when_redis_down(_db_tables):
    """GET /health/ready returns 503 and ready=false when Redis ping fails."""
    from policy_engine.routes.health import get_redis_health_client  # noqa: PLC0415

    bad_redis = MagicMock()
    bad_redis.ping.side_effect = ConnectionError("redis down")

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_health_client] = lambda: bad_redis

    with TestClient(app, raise_server_exceptions=True) as c:
        response = c.get("/health/ready")

    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["ready"] is False
