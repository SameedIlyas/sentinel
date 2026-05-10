"""HIPAA §164.312(b) audit-control helper for clinic-tier mutations.

Every clinic CRUD action writes a row to the canonical ``audit_logs``
table.  We use the same table the platform uses for agent activity so a
compliance officer has *one* place to look for "what happened in this
practice."

The user is recorded as a synthetic agent (``user:<user_id>``) so the
existing schema's NOT NULL constraints are satisfied without a
migration.  The original tool name lives under ``tool_name`` (e.g.,
``clinic.tool.create``) and the resource being acted upon is in
``data_touched``.

PII discipline: this helper itself never logs ``arguments`` containing
free-text user-supplied fields.  Callers are expected to pass only IDs
and short status fields.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from policy_engine.models.audit_log import AuditLog, Decision
from policy_engine.models.user import User


_ALLOWED_DECISIONS = {Decision.ALLOWED, Decision.BLOCKED, Decision.REQUIRES_APPROVAL}


def write_clinic_audit(
    db: Session,
    *,
    user: User,
    org_id: Optional[str],
    action: str,
    system: str,
    data_touched: Iterable[str] = (),
    decision: Decision = Decision.ALLOWED,
    reason: str = "Clinic user action",
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """Persist an audit-log entry for a clinic-tier mutation.

    Returns the new audit log id so callers can chain it onto
    notifications or downstream events.
    """
    if decision not in _ALLOWED_DECISIONS:
        decision = Decision.ALLOWED
    log_id = str(uuid.uuid4())
    db.add(
        AuditLog(
            id=log_id,
            timestamp=datetime.utcnow(),
            agent_id=f"user:{user.id}",
            agent_name=user.full_name or user.username,
            user_id=user.id,
            tool_name=action,
            arguments={},  # never store free-text — callers pass only IDs
            system_accessed=system,
            data_touched=list(data_touched),
            decision=decision,
            policy_ids=[],
            reason=reason[:500],
            log_metadata={k: v for k, v in (metadata or {}).items() if v is not None},
            organization_id=org_id,
        )
    )
    # Caller owns the commit so the audit lives in the same transaction
    # as the mutation it audits.
    return log_id
