"""Tier-aware route gates.

Single helper module so the predicate ``"is this user on a clinic tier?"``
is computed in one place across all clinic routes.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.models.organization import (
    Organization,
    CLINIC_TIERS,
    is_clinic_tier,
)
from policy_engine.models.user import User


def get_user_tier(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> str:
    """Return the tier string for the current user's org, default 'enterprise'."""
    if not current_user.organization_id:
        return "enterprise"
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        return "enterprise"
    return org.tier or "enterprise"


def get_user_org(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    """Resolve the current user's Organization or 404."""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not attached to an organization",
        )
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return org


def require_clinic_tier(
    org: Organization = Depends(get_user_org),
) -> Organization:
    """403 unless the user's org is on a clinic tier."""
    if not is_clinic_tier(org.tier):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "tier_required",
                "message": "This feature is available on clinic plans only.",
                "current_tier": org.tier,
                "required_tiers": list(CLINIC_TIERS),
            },
        )
    return org


def require_clinic_tier_with_baa(
    org: Organization = Depends(require_clinic_tier),
) -> Organization:
    """403 if the org is on a clinic tier but has not signed its BAA.

    HIPAA §164.502(e) — a covered entity may not allow a business
    associate to create, receive, maintain, or transmit PHI on its
    behalf without a BAA in force.  Apply this gate to every write
    path that the platform may use to govern PHI flow (tool registry,
    policy templates, observation ingest, reports).
    """
    if not org.hipaa_baa_signed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "baa_required",
                "message": (
                    "Your Business Associate Agreement is not on file. "
                    "Sign your BAA in Practice Settings → Compliance "
                    "before using PHI-adjacent features."
                ),
                "current_tier": org.tier,
            },
        )
    return org


def require_min_clinic_tier(min_tier: str):
    """Factory for routes restricted to Standard or Multi-site clinic tiers."""
    order = {
        "clinic_basic": 1,
        "clinic_standard": 2,
        "clinic_multi_site": 3,
    }
    floor = order.get(min_tier, 0)

    def _checker(org: Organization = Depends(require_clinic_tier)) -> Organization:
        if order.get(org.tier, 0) < floor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "tier_upgrade_required",
                    "message": f"This feature requires {min_tier.replace('_', ' ')} or above.",
                    "current_tier": org.tier,
                    "required_tier": min_tier,
                },
            )
        return org

    return _checker
