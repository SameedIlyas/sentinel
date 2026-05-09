"""Tests for the Tier 2 Sprint 1 HITL auto-creation flow.

Covers:
  - trigger_hitl_from_policy creates a HITLReview row when decision is
    require_approval, with priority + risk_score + SLA derived correctly.
  - Decisions other than require_approval do not create reviews.
  - Dedup window prevents duplicate creation for the same agent+tool.
  - Audit trail entry is seeded with a valid hash chain.
  - Generic create_hitl_review path also seeds a chain entry.
"""
from datetime import datetime, timedelta

from policy_engine.models.hitl import HITLReview, HITLAuditTrail
from policy_engine.models.schemas import PolicyCheckRequest, PolicyCheckResponse
from policy_engine.services.hitl_auto_service import (
    SLA_HOURS_BY_PRIORITY,
    create_hitl_review,
    trigger_hitl_from_policy,
)


_DEFAULT_ARGS = {"amount": 5000, "to": "vendor-x"}


def _make_request(
    *,
    tool_name: str = "transfer_funds",
    arguments: dict | None = None,
    agent_id: str = "agent-fin-01",
) -> PolicyCheckRequest:
    return PolicyCheckRequest(
        agent_id=agent_id,
        user_id="user-001",
        tool_name=tool_name,
        arguments=_DEFAULT_ARGS if arguments is None else arguments,
        context={"agent_name": "Finance Bot", "organization_id": "org-1"},
    )


def _make_response(
    *,
    decision: str = "require_approval",
    reason: str = "Transactions over $1,000 require manager approval",
    policy_ids: list[str] | None = None,
    metadata: dict | None = None,
) -> PolicyCheckResponse:
    return PolicyCheckResponse(
        decision=decision,
        reason=reason,
        masked_data=None,
        policy_ids=policy_ids or ["policy-financial-1"],
        metadata=metadata or {},
    )


def test_trigger_hitl_creates_review_for_require_approval(db_session):
    request = _make_request()
    response = _make_response()

    result = trigger_hitl_from_policy(db_session, request, response, audit_log_id="audit-1")

    assert result.created is True
    assert result.review_id is not None

    review = db_session.query(HITLReview).filter_by(id=result.review_id).first()
    assert review is not None
    assert review.status == "pending"
    assert review.priority == "high"  # amount=5000 → high
    assert review.organization_id == "org-1"
    assert review.risk_score >= 60.0
    assert review.sla_deadline is not None
    expected_deadline = datetime.utcnow() + timedelta(
        hours=SLA_HOURS_BY_PRIORITY["high"]
    )
    # ±10 minutes tolerance for test wallclock
    assert abs((review.sla_deadline - expected_deadline).total_seconds()) < 600

    assert review.ai_decision["recommendation"] == "block_pending_review"
    assert review.ai_decision["audit_log_id"] == "audit-1"
    assert review.ai_decision["tool_name"] == "transfer_funds"


def test_trigger_hitl_skips_when_decision_is_allow(db_session):
    request = _make_request()
    response = _make_response(decision="allow", reason="Within policy")

    result = trigger_hitl_from_policy(db_session, request, response)

    assert result.created is False
    assert result.skipped_reason == "not_approval_decision"
    assert db_session.query(HITLReview).count() == 0


def test_trigger_hitl_skips_when_decision_is_block(db_session):
    request = _make_request()
    response = _make_response(decision="block", reason="Over limit")

    result = trigger_hitl_from_policy(db_session, request, response)

    assert result.created is False
    assert db_session.query(HITLReview).count() == 0


def test_trigger_hitl_priority_urgent_for_phi(db_session):
    request = _make_request(tool_name="export_patient_records")
    response = _make_response(reason="PHI export requires data_protection review")

    result = trigger_hitl_from_policy(db_session, request, response)

    review = db_session.query(HITLReview).filter_by(id=result.review_id).first()
    assert review.priority == "urgent"
    expected_deadline = datetime.utcnow() + timedelta(
        hours=SLA_HOURS_BY_PRIORITY["urgent"]
    )
    assert abs((review.sla_deadline - expected_deadline).total_seconds()) < 600


def test_trigger_hitl_priority_urgent_for_large_amount(db_session):
    request = _make_request(arguments={"amount": 50_000})
    response = _make_response()

    result = trigger_hitl_from_policy(db_session, request, response)

    review = db_session.query(HITLReview).filter_by(id=result.review_id).first()
    assert review.priority == "urgent"
    assert review.risk_score >= 80.0


def test_trigger_hitl_priority_medium_for_unknown_tool(db_session):
    request = _make_request(
        tool_name="unknown_tool",
        arguments={},
    )
    response = _make_response(reason="Manual approval required")

    result = trigger_hitl_from_policy(db_session, request, response)

    review = db_session.query(HITLReview).filter_by(id=result.review_id).first()
    assert review.priority == "medium"


def test_trigger_hitl_dedupes_within_window(db_session):
    request = _make_request()
    response = _make_response()

    first = trigger_hitl_from_policy(db_session, request, response)
    second = trigger_hitl_from_policy(db_session, request, response)

    assert first.created is True
    assert second.created is False
    assert second.skipped_reason == "deduplicated"
    assert second.review_id == first.review_id
    assert db_session.query(HITLReview).count() == 1


def test_trigger_hitl_seeds_audit_trail_with_hash_chain(db_session):
    request = _make_request()
    response = _make_response()

    result = trigger_hitl_from_policy(db_session, request, response, audit_log_id="al-1")

    entries = (
        db_session.query(HITLAuditTrail)
        .filter_by(review_id=result.review_id)
        .all()
    )
    assert len(entries) == 1
    entry = entries[0]
    assert entry.action == "auto_create"
    assert entry.actor_id == "system:policy_engine"
    assert entry.new_status == "pending"
    assert entry.entry_hash != ""  # hash chain populated


def test_create_hitl_review_generic_path(db_session):
    review_id = create_hitl_review(
        db_session,
        title="Drift alert: model mc_sepsis PSI=0.45",
        description="Population drift detected on age subgroup",
        ai_decision={"source": "drift_alert", "psi": 0.45},
        risk_score=72.5,
        priority="high",
        organization_id="org-1",
        actor_id="system:drift_monitor",
        seed_action="drift_alert",
    )

    assert review_id is not None
    review = db_session.query(HITLReview).filter_by(id=review_id).first()
    assert review.priority == "high"
    assert review.risk_score == 72.5
    assert review.organization_id == "org-1"

    entries = (
        db_session.query(HITLAuditTrail)
        .filter_by(review_id=review_id)
        .all()
    )
    assert len(entries) == 1
    assert entries[0].actor_id == "system:drift_monitor"
    assert entries[0].action == "auto_create"


def test_create_hitl_review_clamps_risk_score(db_session):
    review_id = create_hitl_review(
        db_session,
        title="x",
        description=None,
        ai_decision={},
        risk_score=999.9,
        priority="medium",
    )
    review = db_session.query(HITLReview).filter_by(id=review_id).first()
    assert review.risk_score == 100.0


def test_create_hitl_review_invalid_priority_falls_back_to_medium(db_session):
    review_id = create_hitl_review(
        db_session,
        title="x",
        description=None,
        ai_decision={},
        risk_score=10.0,
        priority="garbage",
    )
    review = db_session.query(HITLReview).filter_by(id=review_id).first()
    assert review.priority == "medium"
