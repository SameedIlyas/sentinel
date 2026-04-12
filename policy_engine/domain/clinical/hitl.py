"""HITL domain logic — pure Python, hash chain for audit trail integrity."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
import hashlib
import json


class HITLStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class HITLPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class HITLReviewEntity:
    id: str
    title: str
    risk_score: float = 0.0
    status: HITLStatus = HITLStatus.PENDING
    priority: HITLPriority = HITLPriority.MEDIUM
    sla_deadline: Optional[datetime] = None
    description: Optional[str] = None


def is_overdue(review: HITLReviewEntity) -> bool:
    """True if the SLA deadline has passed."""
    if review.sla_deadline is None:
        return False
    now = datetime.now(timezone.utc)
    deadline = review.sla_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return now > deadline


def escalation_tier(review: HITLReviewEntity) -> int:
    """
    0 = on time (>= 6h remaining)
    1 = warning (< 6h remaining, before deadline)
    2 = overdue (just past SLA, < 24h overdue)
    3 = critical (> 24h past SLA)
    """
    if review.sla_deadline is None:
        return 0

    now = datetime.now(timezone.utc)
    deadline = review.sla_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    if now <= deadline:
        # Before deadline — check if warning zone
        time_remaining = (deadline - now).total_seconds()
        # Warning if < 6h remaining
        if time_remaining < 6 * 3600:
            return 1
        return 0
    else:
        # Past deadline
        overdue_seconds = (now - deadline).total_seconds()
        if overdue_seconds > 24 * 3600:
            return 3
        return 2


@dataclass
class HITLAuditEntry:
    actor_id: str
    action: str
    old_status: Optional[str]
    new_status: Optional[str]
    comments: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    entry_hash: str = ""

    def compute_hash(self, prev_hash: str = "") -> str:
        """Compute SHA-256 of (prev_hash + entry content)."""
        content = json.dumps({
            "prev_hash": prev_hash,
            "actor_id": self.actor_id,
            "action": self.action,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "comments": self.comments,
            "timestamp": self.timestamp,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


def build_audit_chain(entries: List[HITLAuditEntry]) -> List[HITLAuditEntry]:
    """Compute hash chain across a list of audit entries (in-place, returns same list)."""
    prev_hash = ""
    for entry in entries:
        entry.entry_hash = entry.compute_hash(prev_hash)
        prev_hash = entry.entry_hash
    return entries


def verify_audit_chain(entries: List[HITLAuditEntry]) -> bool:
    """Returns True if all hashes in the chain are valid."""
    prev_hash = ""
    for entry in entries:
        expected = entry.compute_hash(prev_hash)
        if entry.entry_hash != expected:
            return False
        prev_hash = entry.entry_hash
    return True
