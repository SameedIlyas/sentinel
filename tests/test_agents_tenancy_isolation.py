"""Regression test for CRIT-001 — /v1/agents must be tenant-scoped.

Before the fix, ``policy_engine.routes.agents`` queried ``db.query(Agent)``
without any organization filter, so any authenticated user could
enumerate agents from every tenant. The fix scopes every list/get/update
to ``auth.organization_id`` for everyone except ``SYSTEM_ADMIN``.

Cross-tenant access returns 404 to avoid leaking the existence of
other-tenant rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from policy_engine.auth.jwt_utils import create_access_token, get_password_hash
from policy_engine.database import get_db
from policy_engine.main import app
from policy_engine.models.agent import Agent, AgentStatus
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


def _make_agent(db_session, *, org_id: str, name: str = "probe") -> Agent:
    agent = Agent(
        id=f"agent_{uuid.uuid4().hex[:16]}",
        name=name,
        description="tenant probe",
        owner_user_id="probe-user",
        created_at=datetime.utcnow(),
        last_active=datetime.utcnow(),
        status=AgentStatus.ACTIVE,
        agent_metadata={},
        organization_id=org_id,
    )
    db_session.add(agent)
    db_session.commit()
    return agent


def _client(db_session) -> TestClient:
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=True)


def test_agents_list_scopes_to_caller_org(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)

    agent_a = _make_agent(db_session, org_id=org_a.id, name="a-1")
    agent_b = _make_agent(db_session, org_id=org_b.id, name="b-1")

    try:
        with _client(db_session) as c:
            r = c.get("/v1/agents", headers={"Authorization": f"Bearer {token_a}"})
        assert r.status_code == 200, r.text
        ids = {row["id"] for row in r.json()["agents"]}
        assert agent_a.id in ids
        assert agent_b.id not in ids, "cross-tenant agent leak (CRIT-001)"
    finally:
        app.dependency_overrides.clear()


def test_agents_get_by_id_404s_across_tenants(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    agent_b = _make_agent(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.get(
                f"/v1/agents/{agent_b.id}",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text
    finally:
        app.dependency_overrides.clear()


def test_agents_put_cross_tenant_404s(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    agent_b = _make_agent(db_session, org_id=org_b.id, name="b-original")

    try:
        with _client(db_session) as c:
            r = c.put(
                f"/v1/agents/{agent_b.id}",
                json={"name": "evil-rename"},
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text

        # Verify the row was not modified.
        db_session.refresh(agent_b)
        assert agent_b.name == "b-original"
    finally:
        app.dependency_overrides.clear()


def test_agents_metrics_cross_tenant_404s(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    agent_b = _make_agent(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.get(
                f"/v1/agents/{agent_b.id}/metrics",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text
    finally:
        app.dependency_overrides.clear()


def test_agents_system_admin_sees_all_tenants(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token = _make_user(db_session, org_a, role=UserRole.SYSTEM_ADMIN)
    agent_a = _make_agent(db_session, org_id=org_a.id, name="a")
    agent_b = _make_agent(db_session, org_id=org_b.id, name="b")

    try:
        with _client(db_session) as c:
            r = c.get("/v1/agents", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        ids = {row["id"] for row in r.json()["agents"]}
        assert agent_a.id in ids
        assert agent_b.id in ids
    finally:
        app.dependency_overrides.clear()
