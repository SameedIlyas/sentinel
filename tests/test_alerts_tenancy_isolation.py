"""Regression test for CRIT-001 — /v1/alerts must be tenant-scoped.

Before the fix, ``policy_engine.routes.alerts`` queried
``db.query(Alert)`` without any organization filter. The fix scopes
every list/get/acknowledge to ``auth.organization_id`` for everyone
except ``SYSTEM_ADMIN``.

This includes the mutation endpoint ``POST /{alert_id}/acknowledge`` —
without scoping the underlying ``Alert`` lookup, a cross-tenant caller
can flip another tenant's alerts to ``acknowledged=True``.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from policy_engine.auth.jwt_utils import create_access_token, get_password_hash
from policy_engine.database import get_db
from policy_engine.main import app
from policy_engine.models.alert import Alert, AlertSeverity
from policy_engine.models.organization import Organization
from policy_engine.models.user import User, UserRole


def _make_org(db_session, name: str) -> Organization:
    org = Organization(
        id=str(uuid.uuid4()),
        name=name,
        slug=name,
        tier="enterprise",
    )
    db_session.add(org)
    db_session.commit()
    return org


def _make_user(
    db_session, org: Organization, role: UserRole = UserRole.ORG_ADMIN
) -> tuple[User, str]:
    u = User(
        id=str(uuid.uuid4()),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@test.local",
        password_hash=get_password_hash("x"),
        role=role,
        full_name=f"tenant probe {role.value}",
        is_active=True,
        organization_id=org.id,
    )
    db_session.add(u)
    db_session.commit()
    token = create_access_token(
        {"user_id": u.id, "username": u.username, "role": u.role.value, "org_id": org.id}
    )
    return u, token


def _make_alert(db_session, *, org_id: str, agent_id: str = "probe") -> Alert:
    alert = Alert(
        id=f"alert_{uuid.uuid4().hex[:16]}",
        timestamp=datetime.utcnow(),
        severity=AlertSeverity.MEDIUM,
        alert_type="probe.test",
        agent_id=agent_id,
        description="tenant probe",
        acknowledged=False,
        organization_id=org_id,
    )
    db_session.add(alert)
    db_session.commit()
    return alert


def _client(db_session) -> TestClient:
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=True)


def test_alerts_list_scopes_to_caller_org(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)

    alert_a = _make_alert(db_session, org_id=org_a.id, agent_id="a")
    alert_b = _make_alert(db_session, org_id=org_b.id, agent_id="b")

    try:
        with _client(db_session) as c:
            r = c.get("/v1/alerts", headers={"Authorization": f"Bearer {token_a}"})
        assert r.status_code == 200, r.text
        ids = {row["id"] for row in r.json()["alerts"]}
        assert alert_a.id in ids
        assert alert_b.id not in ids, "cross-tenant alert leak (CRIT-001)"
    finally:
        app.dependency_overrides.clear()


def test_alerts_get_by_id_404s_across_tenants(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    alert_b = _make_alert(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.get(
                f"/v1/alerts/{alert_b.id}",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text
    finally:
        app.dependency_overrides.clear()


def test_alerts_acknowledge_cross_tenant_404s(db_session):
    """The acknowledge endpoint must scope the lookup, not just the list."""
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    alert_b = _make_alert(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.post(
                f"/v1/alerts/{alert_b.id}/acknowledge",
                json={"acknowledged_by": "evil"},
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text

        db_session.refresh(alert_b)
        assert alert_b.acknowledged is False, (
            "cross-tenant acknowledge mutated another tenant's alert"
        )
    finally:
        app.dependency_overrides.clear()


def test_alerts_system_admin_sees_all_tenants(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token = _make_user(db_session, org_a, role=UserRole.SYSTEM_ADMIN)
    alert_a = _make_alert(db_session, org_id=org_a.id)
    alert_b = _make_alert(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.get("/v1/alerts", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        ids = {row["id"] for row in r.json()["alerts"]}
        assert alert_a.id in ids
        assert alert_b.id in ids
    finally:
        app.dependency_overrides.clear()
