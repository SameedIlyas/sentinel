"""Regression test for CRIT-001 — /v1/policies must be tenant-scoped.

Before the fix, ``policy_engine.routes.policies`` queried
``db.query(Policy)`` without any organization filter. The fix scopes
every list/get/update/delete to ``auth.organization_id`` for everyone
except ``SYSTEM_ADMIN``.

POST writes ``organization_id = auth.organization_id`` and ignores any
client-supplied value, so a cross-tenant insert is impossible.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from policy_engine.auth.jwt_utils import create_access_token, get_password_hash
from policy_engine.database import get_db
from policy_engine.main import app
from policy_engine.models.organization import Organization
from policy_engine.models.policy import Policy, PolicyType
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


def _make_policy(db_session, *, org_id: str, name: str = "probe") -> Policy:
    policy = Policy(
        id=f"pol_{uuid.uuid4().hex[:16]}",
        name=name,
        description="tenant probe",
        policy_type=PolicyType.ACCESS_CONTROL,
        rules=[
            {
                "id": "r-1",
                "description": "probe",
                "conditions": [{"field": "tool_name", "operator": "eq", "value": "x"}],
                "action": "allow",
                "parameters": None,
            }
        ],
        applies_to=["*"],
        priority=0,
        enabled=True,
        created_by="probe-user",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        organization_id=org_id,
    )
    db_session.add(policy)
    db_session.commit()
    return policy


def _client(db_session) -> TestClient:
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=True)


def test_policies_list_scopes_to_caller_org(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)

    pol_a = _make_policy(db_session, org_id=org_a.id, name="a-pol")
    pol_b = _make_policy(db_session, org_id=org_b.id, name="b-pol")

    try:
        with _client(db_session) as c:
            r = c.get("/v1/policies", headers={"Authorization": f"Bearer {token_a}"})
        assert r.status_code == 200, r.text
        ids = {row["id"] for row in r.json()["policies"]}
        assert pol_a.id in ids
        assert pol_b.id not in ids, "cross-tenant policy leak (CRIT-001)"
    finally:
        app.dependency_overrides.clear()


def test_policies_get_by_id_404s_across_tenants(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    pol_b = _make_policy(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.get(
                f"/v1/policies/{pol_b.id}",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text
    finally:
        app.dependency_overrides.clear()


def test_policies_put_cross_tenant_404s(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    pol_b = _make_policy(db_session, org_id=org_b.id, name="b-original")

    try:
        with _client(db_session) as c:
            r = c.put(
                f"/v1/policies/{pol_b.id}",
                json={"name": "evil-rename"},
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text

        db_session.refresh(pol_b)
        assert pol_b.name == "b-original"
    finally:
        app.dependency_overrides.clear()


def test_policies_delete_cross_tenant_404s(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    pol_b = _make_policy(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.delete(
                f"/v1/policies/{pol_b.id}",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text

        # Row must still exist.
        survived = db_session.query(Policy).filter(Policy.id == pol_b.id).first()
        assert survived is not None
    finally:
        app.dependency_overrides.clear()


def test_policies_post_forces_caller_org(db_session):
    """A POST must write organization_id from auth, not from the payload."""
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)

    payload = {
        "name": "new-pol",
        "policy_type": "access_control",
        "rules": [
            {
                "conditions": [
                    {"field": "tool_name", "operator": "eq", "value": "x"}
                ],
                "action": "allow",
            }
        ],
        "applies_to": ["*"],
        # Attempt to mis-assign to org_b — the route must ignore this.
        "organization_id": org_b.id,
    }
    try:
        with _client(db_session) as c:
            r = c.post(
                "/v1/policies",
                json=payload,
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 201, r.text
        pol_id = r.json()["id"]
        row = db_session.query(Policy).filter(Policy.id == pol_id).first()
        assert row is not None
        assert row.organization_id == org_a.id, (
            "POST must force organization_id from the auth context"
        )
    finally:
        app.dependency_overrides.clear()


def test_policies_system_admin_sees_all_tenants(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token = _make_user(db_session, org_a, role=UserRole.SYSTEM_ADMIN)
    pol_a = _make_policy(db_session, org_id=org_a.id)
    pol_b = _make_policy(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.get("/v1/policies", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        ids = {row["id"] for row in r.json()["policies"]}
        assert pol_a.id in ids
        assert pol_b.id in ids
    finally:
        app.dependency_overrides.clear()
