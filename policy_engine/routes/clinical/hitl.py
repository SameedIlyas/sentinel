"""HITL Validation Portal endpoints.

Tenancy: every list/get/assign/approve/reject/escalate/audit-trail
endpoint is scoped to the caller's ``organization_id``. SYSTEM_ADMIN
bypasses the scope so platform operators can still triage cross-tenant.
Cross-tenant access returns 404, never 403, to avoid leaking the
existence of other-tenant rows (CRIT-004).

POST writes ``organization_id = current_user.organization_id`` and
ignores any client-supplied value, so a cross-tenant insert is
impossible.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.query import Query as SAQuery
from typing import List, Optional
import uuid
from datetime import datetime

from policy_engine.database import get_db
from policy_engine.auth.rbac import get_current_user
from policy_engine.models.user import User, UserRole, has_permission
from policy_engine.models.hitl import HITLReview, HITLAuditTrail, HITLAssignment
from policy_engine.domain.clinical.hitl import (
    HITLAuditEntry,
    build_audit_chain,
    verify_audit_chain,
)
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class HITLReviewCreate(BaseModel):
    title: str
    description: Optional[str] = None
    ai_decision: Optional[dict] = None
    risk_score: float = 0.0
    priority: str = "medium"
    sla_deadline: Optional[datetime] = None
    # ``organization_id`` from the payload is IGNORED — the route forces
    # it from the authenticated user's org. Field kept for backward
    # compatibility but never trusted.
    organization_id: Optional[str] = None


class HITLAssignRequest(BaseModel):
    assigned_to: str


class HITLActionRequest(BaseModel):
    comments: Optional[str] = None


class HITLReviewResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    ai_decision: dict = {}
    risk_score: float
    status: str
    priority: str
    assigned_to: Optional[str] = None
    sla_deadline: Optional[datetime] = None
    organization_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_system_admin(user: User) -> bool:
    return user.role == UserRole.SYSTEM_ADMIN


def _scope_to_tenant(query: SAQuery, user: User) -> SAQuery:
    """Scope a HITLReview query to the caller's org (SYSTEM_ADMIN bypass)."""
    if _is_system_admin(user):
        return query
    return query.filter(HITLReview.organization_id == user.organization_id)


def _check_permission(current_user: User, action: str) -> None:
    if not has_permission(current_user.role, "hitl_reviews", action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to {action} hitl_reviews",
        )


def _get_review_or_404(
    review_id: str, db: Session, current_user: User
) -> HITLReview:
    """Fetch a review scoped to the caller's org. 404 on miss or cross-tenant."""
    review = _scope_to_tenant(
        db.query(HITLReview).filter(HITLReview.id == review_id),
        current_user,
    ).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="HITL review not found"
        )
    return review


def _to_response(review: HITLReview) -> dict:
    return {
        "id": review.id,
        "title": review.title,
        "description": review.description,
        "ai_decision": review.ai_decision or {},
        "risk_score": review.risk_score,
        "status": review.status,
        "priority": review.priority,
        "assigned_to": review.assigned_to,
        "sla_deadline": review.sla_deadline,
        "organization_id": review.organization_id,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


def _append_audit_entry(
    review_id: str,
    actor_id: str,
    action: str,
    old_status: Optional[str],
    new_status: Optional[str],
    comments: Optional[str],
    db: Session,
) -> None:
    """Append a single audit entry. Append-only — NEVER updates prior rows.

    CRIT-002 fix — historically this rebuilt the entire chain hash on
    every append, which rewrote prior rows' ``entry_hash`` columns and
    defeated the immutability contract. The verifier subsequently always
    returned True because the chain was being normalised on every write.

    Contract:
      1. Read the last persisted entry's ``entry_hash``.
      2. Compute the new entry's hash from that ``prev_hash``.
      3. INSERT the new row. Never UPDATE.
    """
    # CRIT-002 — query for the most recent existing entry only. The
    # previous code loaded the entire chain just to rebuild every hash.
    last_entry = (
        db.query(HITLAuditTrail)
        .filter(HITLAuditTrail.review_id == review_id)
        .order_by(HITLAuditTrail.timestamp.desc())
        .first()
    )
    prev_hash = (last_entry.entry_hash if last_entry else "") or ""

    now = datetime.utcnow()

    # CRIT-003 — feed the *datetime* into the domain entry; the domain
    # normalises both write- and verify-time timestamps to the same
    # offset-free string, so the hash matches on read-back.
    new_domain_entry = HITLAuditEntry(
        actor_id=actor_id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        comments=comments,
        timestamp=now.isoformat(),
        entry_hash="",
    )
    new_domain_entry.entry_hash = new_domain_entry.compute_hash(prev_hash)

    new_db_entry = HITLAuditTrail(
        id=str(uuid.uuid4()),
        review_id=review_id,
        actor_id=actor_id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        comments=comments,
        timestamp=now,
        entry_hash=new_domain_entry.entry_hash,
    )
    db.add(new_db_entry)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/hitl/reviews", response_model=List[HITLReviewResponse])
def list_hitl_reviews(
    status_filter: Optional[str] = None,
    priority: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    query = _scope_to_tenant(db.query(HITLReview), current_user)
    if status_filter:
        query = query.filter(HITLReview.status == status_filter)
    if priority:
        query = query.filter(HITLReview.priority == priority)
    reviews = query.all()
    return [_to_response(r) for r in reviews]


@router.post("/hitl/reviews", status_code=status.HTTP_201_CREATED)
def create_hitl_review(
    payload: HITLReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "create")
    now = datetime.utcnow()
    review = HITLReview(
        id=str(uuid.uuid4()),
        title=payload.title,
        description=payload.description,
        ai_decision=payload.ai_decision or {},
        risk_score=payload.risk_score,
        status="pending",
        priority=payload.priority,
        sla_deadline=payload.sla_deadline,
        # Force tenancy from the auth context. Never trust a client value.
        organization_id=current_user.organization_id,
        created_at=now,
        updated_at=now,
    )
    db.add(review)
    db.flush()

    _append_audit_entry(
        review_id=review.id,
        actor_id=current_user.id,
        action="create",
        old_status=None,
        new_status="pending",
        comments=None,
        db=db,
    )

    db.commit()
    db.refresh(review)
    return _to_response(review)


@router.get("/hitl/reviews/{review_id}")
def get_hitl_review(
    review_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    review = _get_review_or_404(review_id, db, current_user)
    return _to_response(review)


@router.patch("/hitl/reviews/{review_id}/assign")
def assign_hitl_review(
    review_id: str,
    payload: HITLAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "update")
    review = _get_review_or_404(review_id, db, current_user)
    old_status = review.status

    review.assigned_to = payload.assigned_to
    review.status = "in_review"
    review.updated_at = datetime.utcnow()

    assignment = HITLAssignment(
        id=str(uuid.uuid4()),
        review_id=review_id,
        assigned_to=payload.assigned_to,
        assigned_by=current_user.id,
        assigned_at=datetime.utcnow(),
    )
    db.add(assignment)

    _append_audit_entry(
        review_id=review_id,
        actor_id=current_user.id,
        action="assign",
        old_status=old_status,
        new_status="in_review",
        comments=None,
        db=db,
    )

    db.commit()
    db.refresh(review)
    return _to_response(review)


@router.post("/hitl/reviews/{review_id}/approve")
def approve_hitl_review(
    review_id: str,
    payload: HITLActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "update")
    review = _get_review_or_404(review_id, db, current_user)
    old_status = review.status

    review.status = "approved"
    review.updated_at = datetime.utcnow()

    _append_audit_entry(
        review_id=review_id,
        actor_id=current_user.id,
        action="approve",
        old_status=old_status,
        new_status="approved",
        comments=payload.comments,
        db=db,
    )

    db.commit()
    db.refresh(review)
    return _to_response(review)


@router.post("/hitl/reviews/{review_id}/reject")
def reject_hitl_review(
    review_id: str,
    payload: HITLActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "update")
    review = _get_review_or_404(review_id, db, current_user)
    old_status = review.status

    review.status = "rejected"
    review.updated_at = datetime.utcnow()

    _append_audit_entry(
        review_id=review_id,
        actor_id=current_user.id,
        action="reject",
        old_status=old_status,
        new_status="rejected",
        comments=payload.comments,
        db=db,
    )

    db.commit()
    db.refresh(review)
    return _to_response(review)


@router.post("/hitl/reviews/{review_id}/escalate")
def escalate_hitl_review(
    review_id: str,
    payload: HITLActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "update")
    review = _get_review_or_404(review_id, db, current_user)
    old_status = review.status

    review.status = "escalated"
    review.updated_at = datetime.utcnow()

    _append_audit_entry(
        review_id=review_id,
        actor_id=current_user.id,
        action="escalate",
        old_status=old_status,
        new_status="escalated",
        comments=payload.comments,
        db=db,
    )

    db.commit()
    db.refresh(review)
    return _to_response(review)


@router.get("/hitl/reviews/{review_id}/audit-trail")
def get_audit_trail(
    review_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    # Use the scope helper so cross-tenant audit-trail probes 404 before
    # touching the audit table at all.
    _get_review_or_404(review_id, db, current_user)

    db_entries = (
        db.query(HITLAuditTrail)
        .filter(HITLAuditTrail.review_id == review_id)
        .order_by(HITLAuditTrail.timestamp)
        .all()
    )

    domain_entries = [
        HITLAuditEntry(
            actor_id=e.actor_id or "",
            action=e.action,
            old_status=e.old_status,
            new_status=e.new_status,
            comments=e.comments,
            timestamp=e.timestamp.isoformat() if e.timestamp else "",
            entry_hash=e.entry_hash or "",
        )
        for e in db_entries
    ]
    chain_valid = verify_audit_chain(domain_entries)

    return {
        "review_id": review_id,
        "chain_valid": chain_valid,
        "entries": [
            {
                "id": e.id,
                "actor_id": e.actor_id,
                "action": e.action,
                "old_status": e.old_status,
                "new_status": e.new_status,
                "comments": e.comments,
                "timestamp": e.timestamp,
                "entry_hash": e.entry_hash,
            }
            for e in db_entries
        ],
    }
