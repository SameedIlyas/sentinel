"""HITL auto-creation service.

Bridges policy decisions and downstream events (drift alerts, bias audit
failures, adverse events) into the Human-In-The-Loop review queue.

Tier 2 Sprint 1 — turns the previously decorative `require_approval` policy
action into a fully wired feedback loop: every approval-required decision now
materialises a HITLReview row with risk-weighted priority and SLA.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import logging
import uuid

from sqlalchemy.orm import Session

from policy_engine.models.hitl import HITLReview, HITLAuditTrail
from policy_engine.models.schemas import PolicyCheckRequest, PolicyCheckResponse
from policy_engine.domain.clinical.hitl import HITLAuditEntry, build_audit_chain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SLA & priority policy
# ---------------------------------------------------------------------------

SLA_HOURS_BY_PRIORITY: Dict[str, int] = {
    "urgent": 4,
    "high": 24,
    "medium": 72,
    "low": 168,
}


def _priority_from_request(
    request: PolicyCheckRequest,
    response: PolicyCheckResponse,
) -> str:
    """Pick a HITL priority based on tool name + arguments + policy metadata.

    Heuristics (in priority order):
      - PHI/PII data-protection signals → urgent
      - Financial transactions over $10k → urgent
      - Financial transactions over $1k or admin tools → high
      - Anything else needing approval → medium
    """
    tool_name = (request.tool_name or "").lower()
    arguments = request.arguments or {}
    reason = (response.reason or "").lower()

    if any(kw in reason for kw in ("phi", "hipaa", "pii", "data_protection")):
        return "urgent"

    amount = arguments.get("amount")
    try:
        if amount is not None and float(amount) >= 10_000:
            return "urgent"
        if amount is not None and float(amount) >= 1_000:
            return "high"
    except (TypeError, ValueError):
        pass

    if any(kw in tool_name for kw in (
        "delete", "drop_", "alter_", "modify_budget", "create_purchase_order",
        "publish", "deploy_", "transfer_funds",
    )):
        return "high"

    return "medium"


def _risk_score_from_request(
    request: PolicyCheckRequest,
    response: PolicyCheckResponse,
    priority: str,
) -> float:
    """Compute a 0–100 risk score derived from priority + amount magnitude.

    This score feeds the Risk Portfolio sort order on the HITL queue page.
    Deterministic so it can be re-derived for tests.
    """
    base = {"urgent": 80.0, "high": 60.0, "medium": 35.0, "low": 15.0}[priority]

    arguments = request.arguments or {}
    amount = arguments.get("amount")
    try:
        if amount is not None:
            amount_value = float(amount)
            base += min(15.0, amount_value / 10_000.0)
    except (TypeError, ValueError):
        pass

    return round(min(100.0, max(1.0, base)), 1)


# ---------------------------------------------------------------------------
# Hash-chain helper
# ---------------------------------------------------------------------------

def _seed_audit_entry(
    db: Session,
    review_id: str,
    actor_id: str,
    new_status: str,
    comments: Optional[str],
) -> None:
    """Append the initial 'auto_create' audit trail entry with hash chain."""
    now = datetime.utcnow()
    domain_entry = HITLAuditEntry(
        actor_id=actor_id,
        action="auto_create",
        old_status=None,
        new_status=new_status,
        comments=comments,
        timestamp=now.isoformat(),
        entry_hash="",
    )
    build_audit_chain([domain_entry])

    db.add(HITLAuditTrail(
        id=str(uuid.uuid4()),
        review_id=review_id,
        actor_id=actor_id,
        action="auto_create",
        old_status=None,
        new_status=new_status,
        comments=comments,
        timestamp=now,
        entry_hash=domain_entry.entry_hash,
    ))


# ---------------------------------------------------------------------------
# Public API: trigger_hitl
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HITLAutoCreateResult:
    """Outcome of an auto-create attempt."""
    review_id: Optional[str]
    created: bool
    skipped_reason: Optional[str] = None


def trigger_hitl_from_policy(
    db: Session,
    request: PolicyCheckRequest,
    response: PolicyCheckResponse,
    audit_log_id: Optional[str] = None,
) -> HITLAutoCreateResult:
    """Auto-create a HITLReview row when policy returns require_approval.

    Idempotent within a 5-minute window: if a HITL review already exists for
    the same agent/tool combination in the last 5 minutes, we skip — same
    deduplication contract as alert_service so tight retry loops don't flood
    the queue.

    Args:
        db: SQLAlchemy session.
        request: Original policy check request.
        response: Policy decision (must be require_approval to proceed).
        audit_log_id: Linked audit_logs.id for traceability (stored in metadata).

    Returns:
        HITLAutoCreateResult with the new review_id (or skip reason).
    """
    if response.decision != "require_approval":
        return HITLAutoCreateResult(review_id=None, created=False,
                                    skipped_reason="not_approval_decision")

    try:
        # Dedup: skip if an identical pending review was created recently
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        existing = (
            db.query(HITLReview)
            .filter(
                HITLReview.status == "pending",
                HITLReview.title.like(f"%{request.tool_name}%{request.agent_id}%"),
                HITLReview.created_at >= cutoff,
            )
            .first()
        )
        if existing is not None:
            logger.info(
                "HITL auto-create deduplicated (within 5-min window): "
                f"existing review_id={existing.id}"
            )
            return HITLAutoCreateResult(review_id=existing.id, created=False,
                                        skipped_reason="deduplicated")

        priority = _priority_from_request(request, response)
        risk_score = _risk_score_from_request(request, response, priority)
        sla_hours = SLA_HOURS_BY_PRIORITY.get(priority, 72)

        agent_name = (request.context or {}).get("agent_name", request.agent_id)

        title = (
            f"Approval needed: {request.tool_name} by {agent_name} "
            f"({request.agent_id})"
        )
        # Truncate to keep DB-safe even with very long tool names
        title = title[:255]

        ai_decision: Dict[str, Any] = {
            "recommendation": "block_pending_review",
            "decision": response.decision,
            "reason": response.reason,
            "policy_ids": list(response.policy_ids or []),
            "tool_name": request.tool_name,
            "agent_id": request.agent_id,
            "user_id": request.user_id,
            "audit_log_id": audit_log_id,
            "metadata": dict(response.metadata or {}),
        }

        review_id = str(uuid.uuid4())
        review = HITLReview(
            id=review_id,
            title=title,
            description=response.reason,
            ai_decision=ai_decision,
            risk_score=risk_score,
            status="pending",
            priority=priority,
            sla_deadline=datetime.utcnow() + timedelta(hours=sla_hours),
            organization_id=(request.context or {}).get("organization_id"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(review)
        db.flush()

        _seed_audit_entry(
            db=db,
            review_id=review_id,
            actor_id="system:policy_engine",
            new_status="pending",
            comments=(
                f"Auto-created from policy decision require_approval. "
                f"Policies={','.join(response.policy_ids or []) or 'n/a'}. "
                f"Audit log={audit_log_id}."
            ),
        )

        db.commit()
        logger.info(
            "HITL review auto-created: id=%s priority=%s sla_hours=%d "
            "agent=%s tool=%s audit_log=%s",
            review_id, priority, sla_hours,
            request.agent_id, request.tool_name, audit_log_id,
        )

        return HITLAutoCreateResult(review_id=review_id, created=True)

    except Exception as exc:
        # Never let HITL-creation failure break the policy-check flow
        logger.error("HITL auto-create failed: %s", exc, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return HITLAutoCreateResult(review_id=None, created=False,
                                    skipped_reason=f"error:{exc}")


# ---------------------------------------------------------------------------
# Generic creator — used by drift / bias / adverse-event flows in later sprints
# ---------------------------------------------------------------------------

def create_hitl_review(
    db: Session,
    *,
    title: str,
    description: Optional[str],
    ai_decision: Dict[str, Any],
    risk_score: float,
    priority: str = "medium",
    sla_hours: Optional[int] = None,
    organization_id: Optional[str] = None,
    actor_id: str = "system:auto",
    seed_action: str = "auto_create",
) -> Optional[str]:
    """Generic HITL review creator. Returns the new review_id, or None on error."""
    try:
        priority = priority if priority in SLA_HOURS_BY_PRIORITY else "medium"
        if sla_hours is None:
            sla_hours = SLA_HOURS_BY_PRIORITY[priority]

        review_id = str(uuid.uuid4())
        now = datetime.utcnow()
        review = HITLReview(
            id=review_id,
            title=title[:255],
            description=description,
            ai_decision=ai_decision or {},
            risk_score=round(min(100.0, max(0.0, risk_score)), 1),
            status="pending",
            priority=priority,
            sla_deadline=now + timedelta(hours=sla_hours),
            organization_id=organization_id,
            created_at=now,
            updated_at=now,
        )
        db.add(review)
        db.flush()

        _seed_audit_entry(
            db=db,
            review_id=review_id,
            actor_id=actor_id,
            new_status="pending",
            comments=f"{seed_action}: {description or title}"[:1000],
        )

        db.commit()
        logger.info(
            "HITL review created via %s: id=%s priority=%s",
            seed_action, review_id, priority,
        )
        return review_id
    except Exception as exc:
        logger.error("create_hitl_review failed: %s", exc, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return None
