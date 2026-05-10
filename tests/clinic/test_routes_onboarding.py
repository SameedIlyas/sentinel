"""Integration tests for /v1/clinic/onboarding — wizard state."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.clinic


def test_get_onboarding_default_state(clinic_authed_client) -> None:
    client, _org, _user = clinic_authed_client
    resp = client.get("/v1/clinic/onboarding")
    assert resp.status_code == 200
    body = resp.json()
    assert body["step"] == 0
    assert body["baa_accepted_at"] is None
    assert body["first_tool_registered"] is False
    assert body["extension_enabled"] is False
    assert body["completed_at"] is None


def test_onboarding_blocks_enterprise(db_session, make_clinic_org_factory) -> None:
    """Enterprise users hit require_clinic_tier and get 403."""
    from fastapi.testclient import TestClient
    from policy_engine.database import get_db
    from policy_engine.main import app
    from policy_engine.models.organization import TIER_ENTERPRISE
    from tests.factories.clinic import make_clinic_admin

    org = make_clinic_org_factory(tier=TIER_ENTERPRISE, baa_signed=False)
    _user, jwt = make_clinic_admin(db_session, org)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        c = TestClient(app, raise_server_exceptions=True)
        c.headers.update({"Authorization": f"Bearer {jwt}"})
        resp = c.get("/v1/clinic/onboarding")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403
