"""HITL domain logic — pure Python, hash chain for audit-trail integrity.

CRIT-002 + CRIT-003 (PR #12) — the chain is **append-only**:

1. ``HITLAuditEntry.compute_hash`` accepts an explicit ``prev_hash``
   argument and binds the entry to its persisted predecessor.
2. ``build_audit_chain`` is intended for *fresh* chains only. The
   route's append path must compute the new entry's hash from the
   *last persisted* hash and INSERT a single row; it must never UPDATE
   existing rows.
3. Timestamps are normalised through ``_normalise_timestamp`` so that
   the verifier hashes the same string shape that was hashed at write
   time (CRIT-003 — naive vs offset-aware ISO strings used to disagree).
4. ``verify_audit_chain`` walks the entries and recomputes only the
   *expected* current hash from the *previous persisted* hash — it
   never rewrites prior rows.
"""
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
    """0 = on time, 1 = warning, 2 = overdue, 3 = critical."""
    if review.sla_deadline is None:
        return 0

    now = datetime.now(timezone.utc)
    deadline = review.sla_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    if now <= deadline:
        time_remaining = (deadline - now).total_seconds()
        if time_remaining < 6 * 3600:
            return 1
        return 0
    else:
        overdue_seconds = (now - deadline).total_seconds()
        if overdue_seconds > 24 * 3600:
            return 3
        return 2


def _normalise_timestamp(ts: object) -> str:
    """Return a canonical UTC ISO-8601 string for the hash payload.

    CRIT-003 — write-time and verify-time must hash identical strings.
    The historical code mixed ``datetime.utcnow().isoformat()`` (naive)
    with ``datetime.now(timezone.utc).isoformat()`` (offset-aware) which
    produced *different* strings for the same instant — every verify
    returned False on otherwise-clean chains.

    The normalisation rules:

    - ``datetime`` (naive)  → assume UTC, render as ISO without offset.
    - ``datetime`` (aware)  → convert to UTC, render as ISO without offset.
    - ``str``               → strip any trailing 'Z' / '+00:00' so the
                              two shapes converge on the same string.
    - anything else         → ``str(ts)`` so the call never crashes.
    """
    if isinstance(ts, datetime):
        if ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        return ts.isoformat()
    if isinstance(ts, str):
        s = ts
        if s.endswith("Z"):
            s = s[:-1]
        if s.endswith("+00:00"):
            s = s[:-6]
        return s
    return str(ts)


@dataclass
class HITLAuditEntry:
    actor_id: str
    action: str
    old_status: Optional[str]
    new_status: Optional[str]
    comments: Optional[str]
    timestamp: str = field(
        default_factory=lambda: _normalise_timestamp(datetime.now(timezone.utc))
    )
    entry_hash: str = ""

    def compute_hash(self, prev_hash: str = "") -> str:
        """Compute SHA-256 of (prev_hash + entry content).

        CRIT-002 — callers MUST pass the *previously persisted* hash.
        Re-hashing the chain on every append (the historical bug) rewrites
        prior rows and turns the chain into a sandcastle.
        """
        content = json.dumps(
            {
                "prev_hash": prev_hash,
                "actor_id": self.actor_id,
                "action": self.action,
                "old_status": self.old_status,
                "new_status": self.new_status,
                "comments": self.comments,
                # CRIT-003 — always hash the normalised string shape so
                # write and verify agree.
                "timestamp": _normalise_timestamp(self.timestamp),
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()


def build_audit_chain(entries: List[HITLAuditEntry]) -> List[HITLAuditEntry]:
    """Compute hash chain across a list of audit entries.

    Intended for **fresh** chains (e.g. test fixtures, one-time
    backfill). The route's append path MUST NOT call this on the full
    chain — that's the CRIT-002 bug. Instead, compute the new entry's
    hash from the last persisted entry's hash.
    """
    prev_hash = ""
    for entry in entries:
        entry.entry_hash = entry.compute_hash(prev_hash)
        prev_hash = entry.entry_hash
    return entries


def verify_audit_chain(entries: List[HITLAuditEntry]) -> bool:
    """Returns True if every hash in the chain is consistent.

    Read-only — never mutates ``entries``. The verifier recomputes the
    expected hash from the *previous persisted* hash and compares
    against the stored value.
    """
    prev_hash = ""
    for entry in entries:
        expected = entry.compute_hash(prev_hash)
        if entry.entry_hash != expected:
            return False
        prev_hash = entry.entry_hash
    return True
