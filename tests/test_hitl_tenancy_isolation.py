"""Regression test for CRIT-004 — /v1/clinical/hitl/* must be tenant-scoped.

Before the fix, ``_get_review_or_404`` filtered only by ``id``, so an
ORG_ADMIN at clinic A could read, assign, approve, reject, escalate, or
view the audit trail of clinic B's HITL reviews. The fix scopes every
endpoint by the caller's ``organization_id`` (SYSTEM_ADMIN bypass), and
the POST forces ``organization_id`` from the auth context, ignoring any
client-supplied value.

All cross-tenant probes must return 404, never 403, to avoid leaking the
existence of other-tenant rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from policy_engine.auth.jwt_utils import create_access_token, get_password_hash
from policy_engine.database import get_db
from policy_engine.main import app
from policy_engine.models.hitl import HITLReview, HITLAuditTrail
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


def _make_review(db_session, *, org_id: str, title: str = "probe") -> HITLReview:
    now = datetime.utcnow()
    review = HITLReview(
        id=str(uuid.uuid4()),
        title=title,
        description="tenant probe",
        ai_decision={},
        risk_score=0.5,
        status="pending",
        priority="medium",
        organization_id=org_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(review)
    db_session.commit()
    return review


def _client(db_session) -> TestClient:
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=True)


def test_hitl_list_scopes_to_caller_org(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)

    r_a = _make_review(db_session, org_id=org_a.id, title="a-review")
    r_b = _make_review(db_session, org_id=org_b.id, title="b-review")

    try:
        with _client(db_session) as c:
            r = c.get(
                "/v1/clinical/hitl/reviews",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 200, r.text
        ids = {row["id"] for row in r.json()}
        assert r_a.id in ids
        assert r_b.id not in ids, "cross-tenant HITL leak (CRIT-004)"
    finally:
        app.dependency_overrides.clear()


def test_hitl_get_cross_tenant_404s(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    r_b = _make_review(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.get(
                f"/v1/clinical/hitl/reviews/{r_b.id}",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "action",
    ["approve", "reject", "escalate"],
)
def test_hitl_mutations_cross_tenant_404_and_no_audit_row(
    db_session, action: str
):
    """A cross-tenant POST must 404 and write no audit row."""
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    r_b = _make_review(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.post(
                f"/v1/clinical/hitl/reviews/{r_b.id}/{action}",
                json={"comments": "evil"},
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text

        # Confirm: no audit row was created for the targeted review.
        trail = (
            db_session.query(HITLAuditTrail)
            .filter(HITLAuditTrail.review_id == r_b.id)
            .all()
        )
        assert trail == [], (
            f"cross-tenant {action} wrote an audit row for another tenant's review"
        )
        # Confirm: the underlying review status was not mutated.
        db_session.refresh(r_b)
        assert r_b.status == "pending"
    finally:
        app.dependency_overrides.clear()


def test_hitl_assign_cross_tenant_404s(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    r_b = _make_review(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.patch(
                f"/v1/clinical/hitl/reviews/{r_b.id}/assign",
                json={"assigned_to": "evil"},
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text
        db_session.refresh(r_b)
        assert r_b.assigned_to is None
    finally:
        app.dependency_overrides.clear()


def test_hitl_audit_trail_cross_tenant_404s(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)
    r_b = _make_review(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.get(
                f"/v1/clinical/hitl/reviews/{r_b.id}/audit-trail",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 404, r.text
    finally:
        app.dependency_overrides.clear()


def test_hitl_post_forces_caller_org(db_session):
    """A POST must write organization_id from auth, not from the payload."""
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token_a = _make_user(db_session, org_a)

    payload = {
        "title": "new",
        "description": "test",
        "ai_decision": {},
        "risk_score": 0.0,
        "priority": "low",
        # Attempt to mis-assign to org_b — the route must ignore this.
        "organization_id": org_b.id,
    }
    try:
        with _client(db_session) as c:
            r = c.post(
                "/v1/clinical/hitl/reviews",
                json=payload,
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert r.status_code == 201, r.text
        review_id = r.json()["id"]
        row = (
            db_session.query(HITLReview)
            .filter(HITLReview.id == review_id)
            .first()
        )
        assert row is not None
        assert row.organization_id == org_a.id, (
            "POST must force organization_id from the auth context"
        )
    finally:
        app.dependency_overrides.clear()


def test_hitl_system_admin_sees_all_tenants(db_session):
    org_a = _make_org(db_session, "org-a")
    org_b = _make_org(db_session, "org-b")
    _, token = _make_user(db_session, org_a, role=UserRole.SYSTEM_ADMIN)
    r_a = _make_review(db_session, org_id=org_a.id)
    r_b = _make_review(db_session, org_id=org_b.id)

    try:
        with _client(db_session) as c:
            r = c.get(
                "/v1/clinical/hitl/reviews",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200, r.text
        ids = {row["id"] for row in r.json()}
        assert r_a.id in ids
        assert r_b.id in ids
    finally:
        app.dependency_overrides.clear()
