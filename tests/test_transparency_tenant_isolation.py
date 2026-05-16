"""Regression test for HIGH-004 — transparency update/publish tenant check.

`update_transparency_record` and `publish_transparency_record` historically
only checked role (`_require_admin`). An ORG_ADMIN at org A could PUT or
POST publish against a record owned by org B and overwrite the published
content. SYSTEM_ADMIN is global by design and must remain so.
"""
import os
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_transparency_tenant.db")
os.environ.setdefault("SECRET_KEY", "test-secret-tenant-iso-xyz-abc")


def _ensure_tables():
    import policy_engine.main  # noqa: F401
    from policy_engine.database import Base, engine
    Base.metadata.create_all(bind=engine)


def _client():
    from fastapi.testclient import TestClient
    from policy_engine.main import app
    return TestClient(app, raise_server_exceptions=False)


def _db():
    from policy_engine.database import SessionLocal
    return SessionLocal()


def _make_user(db, *, role, organization_id):
    from policy_engine.models.user import User
    from policy_engine.auth.jwt_utils import create_access_token, get_password_hash

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        username=f"u_{user_id[:8]}",
        email=f"u_{user_id[:8]}@t.com",
        password_hash=get_password_hash("TestPass123!"),
        role=role,
        organization_id=organization_id,
        full_name="Test User",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    token = create_access_token({
        "user_id": user_id,
        "username": user.username,
        "role": role.value if hasattr(role, "value") else str(role),
    })
    return {
        "Authorization": f"Bearer {token}",
        "X-API-Key": "dummy-bypass-csrf",
    }, user


def _create_record_for_org(db, *, organization_id, created_by):
    from policy_engine.models.transparency import TransparencyRecordModel
    rec = TransparencyRecordModel(
        id=str(uuid.uuid4()),
        model_name="org-b model",
        model_version="1.0",
        algorithm_description="desc",
        plain_language_summary=(
            "This AI model assists clinicians with risk stratification "
            "based on validated retrospective data."
        ),
        evidence_base="study",
        intended_population="adults",
        known_limitations="limited",
        performance_summary={},
        bias_considerations=None,
        regulatory_status=None,
        published_at=None,
        version_number=1,
        organization_id=organization_id,
        created_by=created_by,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _valid_payload():
    return {
        "model_name": "tampered",
        "model_version": "9.9",
        "algorithm_description": "tampered",
        "plain_language_summary": (
            "Tampered content from a different organisation's admin "
            "attempting to overwrite this published record."
        ),
        "evidence_base": "fake",
        "intended_population": "anyone",
        "known_limitations": "none claimed",
    }


def test_org_admin_cannot_update_other_orgs_record():
    from policy_engine.models.user import UserRole
    _ensure_tables()
    client = _client()
    db = _db()
    try:
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())
        headers_a, user_a = _make_user(db, role=UserRole.ORG_ADMIN, organization_id=org_a)
        _, user_b = _make_user(db, role=UserRole.ORG_ADMIN, organization_id=org_b)
        record = _create_record_for_org(db, organization_id=org_b, created_by=user_b.id)

        resp = client.put(
            f"/v1/transparency/{record.id}",
            json=_valid_payload(),
            headers=headers_a,
        )
        assert resp.status_code in (403, 404), resp.text
        db.refresh(record)
        assert record.model_name == "org-b model", "cross-tenant update altered the record"
    finally:
        db.close()


def test_org_admin_cannot_publish_other_orgs_record():
    from policy_engine.models.user import UserRole
    _ensure_tables()
    client = _client()
    db = _db()
    try:
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())
        headers_a, _ = _make_user(db, role=UserRole.ORG_ADMIN, organization_id=org_a)
        _, user_b = _make_user(db, role=UserRole.ORG_ADMIN, organization_id=org_b)
        record = _create_record_for_org(db, organization_id=org_b, created_by=user_b.id)

        resp = client.post(
            f"/v1/transparency/{record.id}/publish",
            headers=headers_a,
        )
        assert resp.status_code in (403, 404), resp.text
        db.refresh(record)
        assert record.published_at is None, "cross-tenant publish set published_at"
    finally:
        db.close()


def test_system_admin_can_publish_any_org_record():
    """SYSTEM_ADMIN is global by design — positive control."""
    from policy_engine.models.user import UserRole
    _ensure_tables()
    client = _client()
    db = _db()
    try:
        org_b = str(uuid.uuid4())
        headers_sys, _ = _make_user(db, role=UserRole.SYSTEM_ADMIN, organization_id=None)
        _, user_b = _make_user(db, role=UserRole.ORG_ADMIN, organization_id=org_b)
        record = _create_record_for_org(db, organization_id=org_b, created_by=user_b.id)

        resp = client.post(
            f"/v1/transparency/{record.id}/publish",
            headers=headers_sys,
        )
        assert resp.status_code == 200, resp.text
        db.refresh(record)
        assert record.published_at is not None
    finally:
        db.close()
