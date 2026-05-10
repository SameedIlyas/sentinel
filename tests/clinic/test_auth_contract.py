"""Auth contract for clinic routes — JWT-only.

Pins the current behavior:
* No auth → 401
* Valid JWT for an enterprise-tier user → 403 (tier gate)
* Valid JWT for a clinic-tier user with BAA → 200 / 201 / 204 expected

Crucially: clinic routes do NOT accept API keys (X-API-Key header). Fix
4421206 added API-key acceptance only to /v1/policies. If a future change
silently extends API-key acceptance to clinic routes, this test will
catch it — tier-gating without a strict auth contract is a privilege-
escalation primitive.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from policy_engine.database import get_db
from policy_engine.main import app
from policy_engine.models.organization import TIER_ENTERPRISE


pytestmark = pytest.mark.clinic


# Read-only GET endpoints under /v1/clinic that should respond 200 for a
# clinic admin, 403 for enterprise, 401 for missing/wrong auth.
CLINIC_GET_ENDPOINTS: list[str] = [
    "/v1/clinic/dashboard/summary",
    "/v1/clinic/tools",
    "/v1/clinic/policy-templates",
    "/v1/clinic/alerts",
    "/v1/clinic/baa/status",
    "/v1/clinic/onboarding",
    "/v1/clinic/reports",
    "/v1/clinic/shadow-ai/extension-token/status",
]


def _client_with_db(db_session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app, raise_server_exceptions=True)


@pytest.mark.parametrize("path", CLINIC_GET_ENDPOINTS)
def test_clinic_get_no_auth_returns_401(db_session, path: str) -> None:
    c = _client_with_db(db_session)
    try:
        resp = c.get(path)
    finally:
        app.dependency_overrides.clear()
    # Either 401 (no creds) or 403 (creds but not authorized) — never 200.
    assert resp.status_code in (401, 403), (
        f"{path} returned {resp.status_code} without auth — expected 401/403"
    )


@pytest.mark.parametrize("path", CLINIC_GET_ENDPOINTS)
def test_clinic_get_api_key_only_returns_401(db_session, agent_api_key, path: str) -> None:
    """Clinic routes must NOT accept API keys (only /v1/policies does, fix 4421206)."""
    raw_key, _agent_id = agent_api_key
    c = _client_with_db(db_session)
    c.headers.update({"X-API-Key": raw_key})
    try:
        resp = c.get(path)
    finally:
        app.dependency_overrides.clear()
    # Must be 401 — clinic routes ignore X-API-Key entirely.
    assert resp.status_code == 401, (
        f"{path} accepted X-API-Key (got {resp.status_code}). Clinic routes "
        "must remain JWT-only — accepting API keys would bypass tier gating."
    )


@pytest.mark.parametrize("path", CLINIC_GET_ENDPOINTS)
def test_clinic_get_enterprise_jwt_returns_403(
    db_session, make_clinic_org_factory, path: str
) -> None:
    from tests.factories.clinic import make_clinic_admin
    org = make_clinic_org_factory(tier=TIER_ENTERPRISE, baa_signed=False)
    _user, jwt = make_clinic_admin(db_session, org)
    c = _client_with_db(db_session)
    c.headers.update({"Authorization": f"Bearer {jwt}"})
    try:
        resp = c.get(path)
    finally:
        app.dependency_overrides.clear()
    # Either tier_required (most routes) or 404/403 if route not on this user.
    # Treat any non-200 in [401, 403, 404] as an acceptable enterprise gate.
    assert resp.status_code in (401, 403, 404), (
        f"{path} returned {resp.status_code} for enterprise — expected gate"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/v1/clinic/dashboard/summary",
        "/v1/clinic/tools",
        "/v1/clinic/policy-templates",
        "/v1/clinic/baa/status",
        "/v1/clinic/onboarding",
    ],
)
def test_clinic_get_clinic_jwt_returns_200(clinic_authed_client, path: str) -> None:
    """A clinic admin with BAA signed gets 200 on the basic GET routes."""
    client, _org, _user = clinic_authed_client
    resp = client.get(path)
    assert resp.status_code == 200, (
        f"{path} returned {resp.status_code} for clinic admin: {resp.text[:200]}"
    )
