"""Regression test for CRIT-001 — /v1/audit/logs must be tenant-scoped.

Before the fix, the listing endpoint queried ``db.query(AuditLog)`` without
any organization filter, so any authenticated user could enumerate audit
records from every tenant. The fix scopes the query to
``auth.organization_id`` for everyone except ``SYSTEM_ADMIN``.

This test wires a tiny FastAPI app around the production route so the
existing test fixtures (in-memory SQLite, fakeredis) stay in play but the
assertion surface is exactly the /v1/audit/logs contract.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from policy_engine.auth.jwt_utils import create_access_token, get_password_hash
from policy_engine.database import get_db
from policy_engine.main import app
from policy_engine.models.audit_log import AuditLog, Decision
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
    db_session, org: Organization, role: UserRole = UserRole.ADMIN
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


def _make_log(db_session, *, org_id: str, agent_id: str = "a1") -> AuditLog:
    log = AuditLog(
        id=f"audit_{uuid.uuid4().hex[:16]}",
        timestamp=datetime.utcnow(),
        agent_id=agent_id,
        agent_name="probe",
        user_id="probe-user",
        tool_name="probe.tool",
        arguments={},
        system_accessed="probe",
        data_touched=[],
        decision=Decision.ALLOWED,
        policy_ids=[],
        reason="probe",
        log_metadata={},
        organization_id=org_id,
    )
    db_session.add(log)
    db_session.commit()
    return log


def _client(db_session) -> TestClient:
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=True)


def test_audit_list_scopes_to_caller_org(db_session):
    """An ORG_ADMIN at org A must see only org-A logs — not org-B logs."""
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")

    _user_a, token_a = _make_user(db_session, org_a, role=UserRole.ADMIN)

    log_a = _make_log(db_session, org_id=org_a.id, agent_id="a-1")
    log_b = _make_log(db_session, org_id=org_b.id, agent_id="b-1")

    try:
        with _client(db_session) as c:
            r = c.get("/v1/audit/logs", headers={"Authorization": f"Bearer {token_a}"})
        assert r.status_code == 200, r.text
        body = r.json()
        ids = {row["id"] for row in body["logs"]}
        assert log_a.id in ids
        assert log_b.id not in ids, "cross-tenant audit-log leak (CRIT-001)"
    finally:
        app.dependency_overrides.clear()


def test_audit_get_by_id_404s_across_tenants(db_session):
    """GET /v1/audit/logs/{id} must 404 when the log belongs to another tenant."""
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _user_a, token_a = _make_user(db_session, org_a)
    log_b = _make_log(db_session, org_id=org_b.id, agent_id="b-only")

    try:
        with _client(db_session) as c:
            r = c.get(
                f"/v1/audit/logs/{log_b.id}",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text
    finally:
        app.dependency_overrides.clear()


def test_audit_system_admin_sees_all_tenants(db_session):
    """SYSTEM_ADMIN is the documented escape hatch for platform operators."""
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _admin, admin_token = _make_user(db_session, org_a, role=UserRole.SYSTEM_ADMIN)
    log_a = _make_log(db_session, org_id=org_a.id)
    log_b = _make_log(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.get("/v1/audit/logs", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, r.text
        ids = {row["id"] for row in r.json()["logs"]}
        assert log_a.id in ids
        assert log_b.id in ids
    finally:
        app.dependency_overrides.clear()
