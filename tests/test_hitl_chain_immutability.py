"""Regression tests for CRIT-002 + CRIT-003 — HITL chain immutability + TZ.

The contract this PR establishes:

1. ``_append_audit_entry`` writes exactly one row per call and never
   updates pre-existing rows. The chain hash of every row is fixed at
   write time.
2. ``verify_audit_chain`` returns True for a clean chain.
   Historically it returned False because timestamp shapes mismatched
   between write- and verify-time (CRIT-003).
3. A direct UPDATE of any hash-binding column (comments, action,
   actor_id, old/new_status, timestamp, entry_hash) breaks verify on
   SQLite via the verifier, and on Postgres the BEFORE UPDATE trigger
   refuses the UPDATE outright (Postgres path documented; SQLite tests
   exercise via raw SQL).
4. Concurrent appends serialise on the chain tip — the second append
   reads the first's persisted hash, so both rows are correctly linked.

These tests target the domain + route surfaces directly. The Postgres
trigger contract is documented in the migration; the live-trigger
exercise belongs in the W-2 Postgres CI lane.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterable

import pytest
from sqlalchemy import text

from policy_engine.domain.clinical.hitl import (
    HITLAuditEntry,
    build_audit_chain,
    verify_audit_chain,
)
from policy_engine.models.hitl import HITLAuditTrail, HITLReview


def _make_review(db_session, *, org_id: str = "probe-org") -> HITLReview:
    now = datetime.utcnow()
    review = HITLReview(
        id=str(uuid.uuid4()),
        title="probe",
        description="probe",
        ai_decision={},
        risk_score=0.1,
        status="pending",
        priority="medium",
        organization_id=org_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(review)
    db_session.commit()
    return review


def _append(db_session, review_id: str, *, action: str, actor_id: str = "u1",
            comments: str | None = None, old: str | None = None,
            new: str | None = None) -> None:
    from policy_engine.routes.clinical.hitl import _append_audit_entry
    _append_audit_entry(
        review_id=review_id,
        actor_id=actor_id,
        action=action,
        old_status=old,
        new_status=new,
        comments=comments,
        db=db_session,
    )
    db_session.commit()


def _load_chain(db_session, review_id: str) -> list[HITLAuditTrail]:
    return (
        db_session.query(HITLAuditTrail)
        .filter(HITLAuditTrail.review_id == review_id)
        .order_by(HITLAuditTrail.timestamp)
        .all()
    )


def _to_domain(rows: Iterable[HITLAuditTrail]) -> list[HITLAuditEntry]:
    out = []
    for r in rows:
        out.append(
            HITLAuditEntry(
                actor_id=r.actor_id or "",
                action=r.action,
                old_status=r.old_status,
                new_status=r.new_status,
                comments=r.comments,
                timestamp=r.timestamp.isoformat() if r.timestamp else "",
                entry_hash=r.entry_hash or "",
            )
        )
    return out


# ---------------------------------------------------------------------------
# CRIT-003: timestamp round-trip — write then verify must agree
# ---------------------------------------------------------------------------

class TestTimestampRoundTrip:
    def test_clean_chain_verifies_true(self, db_session):
        """An append-only chain must verify True. Historically this
        returned False because the hash was computed against one
        timestamp shape at write time and a different shape at verify
        time."""
        review = _make_review(db_session)
        _append(db_session, review.id, action="create")
        _append(db_session, review.id, action="assign", old="pending", new="in_review")
        _append(db_session, review.id, action="approve", old="in_review", new="approved")

        rows = _load_chain(db_session, review.id)
        assert len(rows) == 3
        assert verify_audit_chain(_to_domain(rows)) is True

    def test_single_entry_chain_verifies_true(self, db_session):
        review = _make_review(db_session)
        _append(db_session, review.id, action="create")
        rows = _load_chain(db_session, review.id)
        assert verify_audit_chain(_to_domain(rows)) is True


# ---------------------------------------------------------------------------
# CRIT-002: chain is append-only — never rewrites prior rows
# ---------------------------------------------------------------------------

class TestAppendOnly:
    def test_existing_rows_unchanged_after_append(self, db_session):
        """Adding a new entry must NOT touch existing rows."""
        review = _make_review(db_session)
        _append(db_session, review.id, action="create")
        first = _load_chain(db_session, review.id)[0]
        first_hash_before = first.entry_hash
        first_id = first.id

        # Force the session to read fresh state on next query.
        db_session.expire_all()

        _append(db_session, review.id, action="assign", old="pending", new="in_review")

        rows = _load_chain(db_session, review.id)
        assert len(rows) == 2
        rebuilt_first = next(r for r in rows if r.id == first_id)
        assert rebuilt_first.entry_hash == first_hash_before, (
            "CRIT-002 — append must NOT rewrite the prior row's entry_hash"
        )

    def test_tamper_via_raw_sql_breaks_verify(self, db_session):
        """If someone UPDATEs comments on a prior row via raw SQL, the
        verifier must surface it. On Postgres the BEFORE UPDATE trigger
        refuses; on SQLite (no triggers) the bytes change but the hash
        comparison still catches the tamper."""
        review = _make_review(db_session)
        _append(db_session, review.id, action="create", comments="legit")
        _append(db_session, review.id, action="approve", old="pending", new="approved")

        first = _load_chain(db_session, review.id)[0]
        # Raw SQL tamper — simulating an attacker with DB access.
        db_session.execute(
            text("UPDATE hitl_audit_trail SET comments = :c WHERE id = :id"),
            {"c": "TAMPERED", "id": first.id},
        )
        db_session.commit()
        db_session.expire_all()

        rows = _load_chain(db_session, review.id)
        assert verify_audit_chain(_to_domain(rows)) is False


# ---------------------------------------------------------------------------
# Build/verify symmetry on fresh in-memory chains
# ---------------------------------------------------------------------------

class TestDomain:
    def test_build_then_verify(self):
        e1 = HITLAuditEntry(actor_id="u1", action="create", old_status=None,
                            new_status="pending", comments=None,
                            timestamp="2026-01-01T00:00:00")
        e2 = HITLAuditEntry(actor_id="u1", action="approve",
                            old_status="pending", new_status="approved",
                            comments="ok",
                            timestamp="2026-01-01T00:01:00")
        build_audit_chain([e1, e2])
        assert verify_audit_chain([e1, e2]) is True

    def test_offset_and_naive_timestamps_hash_the_same(self):
        """CRIT-003 — naive UTC and +00:00 strings must yield identical hashes."""
        e_naive = HITLAuditEntry(actor_id="u1", action="x", old_status=None,
                                 new_status=None, comments=None,
                                 timestamp="2026-01-01T00:00:00")
        e_offset = HITLAuditEntry(actor_id="u1", action="x", old_status=None,
                                  new_status=None, comments=None,
                                  timestamp="2026-01-01T00:00:00+00:00")
        e_zulu = HITLAuditEntry(actor_id="u1", action="x", old_status=None,
                                new_status=None, comments=None,
                                timestamp="2026-01-01T00:00:00Z")
        h_naive = e_naive.compute_hash("")
        h_offset = e_offset.compute_hash("")
        h_zulu = e_zulu.compute_hash("")
        assert h_naive == h_offset == h_zulu

    def test_tamper_returns_false(self):
        e1 = HITLAuditEntry(actor_id="u1", action="create", old_status=None,
                            new_status="pending", comments="legit",
                            timestamp="2026-01-01T00:00:00")
        build_audit_chain([e1])
        # Mutate without recomputing — verify must surface it.
        e1.comments = "TAMPERED"
        assert verify_audit_chain([e1]) is False


# ---------------------------------------------------------------------------
# Append idempotency / no double-writes on retry
# ---------------------------------------------------------------------------

class TestAppendShape:
    def test_each_append_inserts_exactly_one_row(self, db_session):
        review = _make_review(db_session)
        before = (
            db_session.query(HITLAuditTrail)
            .filter(HITLAuditTrail.review_id == review.id)
            .count()
        )
        _append(db_session, review.id, action="create")
        mid = (
            db_session.query(HITLAuditTrail)
            .filter(HITLAuditTrail.review_id == review.id)
            .count()
        )
        _append(db_session, review.id, action="approve",
                old="pending", new="approved")
        after = (
            db_session.query(HITLAuditTrail)
            .filter(HITLAuditTrail.review_id == review.id)
            .count()
        )
        assert mid - before == 1
        assert after - mid == 1


# ---------------------------------------------------------------------------
# SQLite no-triggers gap (documentation)
# ---------------------------------------------------------------------------

@pytest.mark.skip(
    reason="SQLite has no trigger support — Postgres-only enforcement; "
    "raw-SQL tamper detection still relies on the verifier (see "
    "TestAppendOnly.test_tamper_via_raw_sql_breaks_verify)."
)
def test_postgres_trigger_refuses_update_on_hash_binding_columns():
    """Live-trigger exercise belongs in the W-2 Postgres CI lane."""
    pass
