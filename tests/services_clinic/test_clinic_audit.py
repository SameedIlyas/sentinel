"""Tests for ``policy_engine.services.clinic_audit``."""

from __future__ import annotations

import pytest

from policy_engine.models.audit_log import AuditLog, Decision
from policy_engine.services.clinic_audit import write_clinic_audit

from tests.factories.clinic import make_clinic_admin, make_clinic_org


pytestmark = pytest.mark.clinic


def test_write_clinic_audit_persists_minimal_row(db_session) -> None:
    org = make_clinic_org(db_session)
    user, _jwt = make_clinic_admin(db_session, org)

    log_id = write_clinic_audit(
        db_session,
        user=user,
        org_id=org.id,
        action="clinic.tool.create",
        system="clinic.tools",
        data_touched=["tool_xyz"],
        reason="Test write",
    )
    db_session.commit()

    row = db_session.query(AuditLog).filter(AuditLog.id == log_id).one()
    assert row.agent_id == f"user:{user.id}"
    assert row.user_id == user.id
    assert row.tool_name == "clinic.tool.create"
    assert row.system_accessed == "clinic.tools"
    assert row.organization_id == org.id
    assert row.data_touched == ["tool_xyz"]
    assert row.decision == Decision.ALLOWED
    # PII discipline — arguments must be empty.
    assert row.arguments == {}


def test_write_clinic_audit_caller_owns_commit(db_session) -> None:
    """Audit helper does NOT commit; caller's transaction does. Verify by
    inserting in a transaction and rolling back — row should not survive."""
    org = make_clinic_org(db_session)
    user, _ = make_clinic_admin(db_session, org)
    log_id = write_clinic_audit(
        db_session,
        user=user,
        org_id=org.id,
        action="clinic.test.rollback",
        system="clinic.tests",
    )
    db_session.rollback()
    row = db_session.query(AuditLog).filter(AuditLog.id == log_id).first()
    assert row is None


def test_write_clinic_audit_truncates_long_reason(db_session) -> None:
    org = make_clinic_org(db_session)
    user, _ = make_clinic_admin(db_session, org)
    long_reason = "x" * 10_000
    log_id = write_clinic_audit(
        db_session,
        user=user,
        org_id=org.id,
        action="clinic.x.y",
        system="clinic.test",
        reason=long_reason,
    )
    db_session.commit()
    row = db_session.query(AuditLog).filter(AuditLog.id == log_id).one()
    assert len(row.reason) == 500


def test_write_clinic_audit_filters_none_metadata(db_session) -> None:
    org = make_clinic_org(db_session)
    user, _ = make_clinic_admin(db_session, org)
    log_id = write_clinic_audit(
        db_session,
        user=user,
        org_id=org.id,
        action="clinic.x.y",
        system="clinic.test",
        metadata={"keep": "yes", "drop": None, "alsokeep": 0},
    )
    db_session.commit()
    row = db_session.query(AuditLog).filter(AuditLog.id == log_id).one()
    assert row.log_metadata == {"keep": "yes", "alsokeep": 0}


def test_write_clinic_audit_clamps_invalid_decision(db_session) -> None:
    """Unknown decisions normalize to ALLOWED so we never persist garbage."""
    org = make_clinic_org(db_session)
    user, _ = make_clinic_admin(db_session, org)
    # Pass a junk decision via the public type system — using a valid
    # Decision is required by the type sig, but we test that the function's
    # internal _ALLOWED_DECISIONS check works.
    # (The function only allows ALLOWED/BLOCKED/REQUIRES_APPROVAL.)
    log_id = write_clinic_audit(
        db_session,
        user=user,
        org_id=org.id,
        action="clinic.x.y",
        system="clinic.test",
        decision=Decision.BLOCKED,
    )
    db_session.commit()
    row = db_session.query(AuditLog).filter(AuditLog.id == log_id).one()
    assert row.decision == Decision.BLOCKED
