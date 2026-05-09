"""Tenant-context fix for seeded data.

The list endpoints in policy_engine.routes.* filter rows by
``current_user.organization_id``. SQL's three-valued logic means
``WHERE organization_id = NULL`` returns zero rows even when all rows have
``organization_id IS NULL`` — so seeded data without an org silently
disappears from the dashboard.

This script creates a single demo organization (idempotent), assigns every
existing user to it, and back-fills every governance row that has a NULL
``organization_id`` to that org. Run once after the seeders.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime

sys.path.insert(0, ".")

from sqlalchemy import update  # noqa: E402

from policy_engine.database import SessionLocal  # noqa: E402
from policy_engine.models.alert import Alert  # noqa: E402  (no org column — skipped)
from policy_engine.models.bias_audit import BiasAuditModel  # noqa: E402
from policy_engine.models.drift import DriftBaseline  # noqa: E402
from policy_engine.models.hitl import HITLReview  # noqa: E402
from policy_engine.models.model_card import ModelCard  # noqa: E402
from policy_engine.models.organization import Organization  # noqa: E402
from policy_engine.models.policy import Policy  # noqa: E402
from policy_engine.models.post_market import AdverseEvent, PMSReport  # noqa: E402
from policy_engine.models.prior_auth import PriorAuthRecord  # noqa: E402
from policy_engine.models.revenue_cycle import RevenueCycleAudit  # noqa: E402
from policy_engine.models.risk_score import RiskScore, RiskScoreHistory  # noqa: E402
from policy_engine.models.scribe_audit import ScribeAuditModel  # noqa: E402
from policy_engine.models.shadow_ai import ShadowAIAllowlist, ShadowAIDetectionModel  # noqa: E402
from policy_engine.models.technical_file import TechnicalFile  # noqa: E402
from policy_engine.models.transparency import TransparencyRecordModel  # noqa: E402
from policy_engine.models.user import User  # noqa: E402

ORG_NAME = "Acme Demo Hospital"
ORG_SLUG = "acme-demo"


def _ensure_org(db) -> Organization:
    org = db.query(Organization).filter(Organization.slug == ORG_SLUG).first()
    if org is not None:
        return org
    now = datetime.utcnow()
    org = Organization(
        id=f"org_{uuid.uuid4().hex[:12]}",
        name=ORG_NAME,
        slug=ORG_SLUG,
        created_at=now,
        updated_at=now,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    print(f"  Created org: {org.id} ({ORG_NAME})")
    return org


def _assign_users(db, org_id: str) -> int:
    n = (
        db.query(User)
        .filter(User.organization_id.is_(None))
        .update({User.organization_id: org_id}, synchronize_session=False)
    )
    db.commit()
    return n


def _backfill(db, model, org_id: str) -> int:
    if not hasattr(model, "organization_id"):
        return 0
    n = (
        db.query(model)
        .filter(model.organization_id.is_(None))
        .update({model.organization_id: org_id}, synchronize_session=False)
    )
    db.commit()
    return n


def main() -> None:
    print("=== Sentinel — Demo organization + tenant-context fix ===")
    db = SessionLocal()
    try:
        org = _ensure_org(db)
        users_updated = _assign_users(db, org.id)
        print(f"  Assigned {users_updated} user(s) to {org.name}")

        models = [
            Policy, ModelCard, BiasAuditModel, DriftBaseline,
            HITLReview, ShadowAIDetectionModel, ShadowAIAllowlist,
            ScribeAuditModel, TransparencyRecordModel, PriorAuthRecord,
            RevenueCycleAudit, TechnicalFile, AdverseEvent, PMSReport,
            RiskScore, RiskScoreHistory,
        ]
        total = 0
        for model in models:
            n = _backfill(db, model, org.id)
            total += n
            if n:
                print(f"    {model.__tablename__:30s} +{n}")
        print(f"  Total rows back-filled: {total}")
        print("=== Done ===")
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
