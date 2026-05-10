"""Factories for clinic-tier domain rows.

Every factory:
* Returns a fully-persisted ORM instance (``db.commit()`` already called).
* Uses PHI-safe synthetic strings from ``tests.factories.phi_safe``.
* Accepts ``**overrides`` for attributes the caller wants to pin.

Convention: factories never seed Stripe customer ids — those land via
billing webhooks in Phase 3, not as bare fixture state.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from policy_engine.auth.jwt_utils import create_access_token, get_password_hash
from policy_engine.models.clinic import (
    BillingEvent,
    ClinicAiObservation,
    ClinicAiTool,
    ClinicAiToolCategory,
    ClinicAiToolRisk,
    ClinicAiToolStatus,
    ClinicExtensionToken,
    ClinicReportArtifact,
)
from policy_engine.models.organization import (
    Organization,
    OrgType,
    TIER_CLINIC_BASIC,
    TIER_CLINIC_STANDARD,
    TIER_CLINIC_MULTI_SITE,
    TIER_ENTERPRISE,
)
from policy_engine.models.user import User, UserRole

from tests.factories.phi_safe import (
    CLINIC_NAMES,
    CLINIC_SLUGS,
    SAFE_OBSERVATION_HOSTS,
    SAFE_TOOL_FINGERPRINTS,
    SAFE_TOOL_NAMES,
    SAFE_TOOL_NOTES,
    SAFE_TOOL_VENDORS,
    safe_email,
)


def _short(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


# ── Organizations ──────────────────────────────────────────────────────


def make_clinic_org(
    db: Session,
    *,
    tier: str = TIER_CLINIC_STANDARD,
    baa_signed: bool = True,
    name: str | None = None,
    slug: str | None = None,
    stripe_customer_id: str | None = None,
    subscription_status: str = "active",
    **overrides: Any,
) -> Organization:
    """Persist a clinic-tier Organization. Default: standard tier with BAA signed."""
    if tier not in (TIER_CLINIC_BASIC, TIER_CLINIC_STANDARD, TIER_CLINIC_MULTI_SITE):
        # Allow enterprise for negative tier-gating tests.
        if tier != TIER_ENTERPRISE:
            raise ValueError(f"Unknown tier: {tier}")

    settings: dict[str, Any] = {}
    if stripe_customer_id is not None or subscription_status != "active":
        settings["billing"] = {
            "stripe_customer_id": stripe_customer_id,
            "subscription_status": subscription_status,
            "plan": tier,
        }

    org = Organization(
        id=_short("org_"),
        name=name or CLINIC_NAMES[0],
        slug=slug or _short("slug-"),
        org_type=OrgType.HOSPITAL,
        tier=tier,
        settings=settings,
        hipaa_baa_signed=baa_signed,
        hipaa_baa_date=datetime.utcnow() if baa_signed else None,
        is_active=True,
    )
    for key, value in overrides.items():
        setattr(org, key, value)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


# ── Users ──────────────────────────────────────────────────────────────


def make_clinic_admin(
    db: Session,
    org: Organization,
    *,
    role: UserRole = UserRole.ORG_ADMIN,
    username: str | None = None,
) -> tuple[User, str]:
    """Create a clinic admin user attached to ``org`` and return (user, jwt)."""
    uid = _short("usr_")
    user = User(
        id=uid,
        username=username or f"admin_{uid[:8]}",
        email=safe_email(f"admin_{uid[:8]}"),
        password_hash=get_password_hash("testpassword"),
        role=role,
        full_name="Test Clinic Admin",
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # Match production routes/auth.py:105 — get_current_user reads "user_id".
    # The existing tests/conftest.py admin_user_jwt fixture uses "sub" instead,
    # which is broken (silently returns 401) but is never asserted because
    # those tests bypass get_current_user.
    token = create_access_token(
        data={
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value,
        }
    )
    return user, token


# ── Clinic AI tools ────────────────────────────────────────────────────


def make_clinic_tool(
    db: Session,
    org: Organization,
    *,
    name: str | None = None,
    vendor: str | None = None,
    category: ClinicAiToolCategory = ClinicAiToolCategory.AMBIENT_SCRIBE,
    risk_level: ClinicAiToolRisk = ClinicAiToolRisk.LOW,
    status: ClinicAiToolStatus = ClinicAiToolStatus.ACTIVE,
    handles_phi: bool = False,
    notes: str | None = None,
    **overrides: Any,
) -> ClinicAiTool:
    tool = ClinicAiTool(
        id=_short("tool_"),
        org_id=org.id,
        name=name or SAFE_TOOL_NAMES[0],
        vendor=vendor or SAFE_TOOL_VENDORS[0],
        category=category,
        purpose="Used for general clinical workflow assistance.",
        handles_phi=handles_phi,
        risk_level=risk_level,
        status=status,
        notes=notes if notes is not None else SAFE_TOOL_NOTES[0],
        source="manual",
    )
    for key, value in overrides.items():
        setattr(tool, key, value)
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


# ── Clinic AI observations (Shadow AI Lite) ────────────────────────────


def make_clinic_observation(
    db: Session,
    org: Organization,
    *,
    host: str | None = None,
    tool_fingerprint: str | None = None,
    page_url: str | None = None,
    severity: str = "low",
    acknowledged: bool = False,
    **overrides: Any,
) -> ClinicAiObservation:
    """Persist a Shadow AI observation. ``page_url`` is hashed and never stored raw."""
    page_url_hash = (
        hashlib.sha256(page_url.encode("utf-8")).hexdigest() if page_url else None
    )
    obs = ClinicAiObservation(
        id=_short("obs_"),
        org_id=org.id,
        host=host or SAFE_OBSERVATION_HOSTS[0],
        tool_fingerprint=tool_fingerprint or SAFE_TOOL_FINGERPRINTS[0],
        page_url_hash=page_url_hash,
        severity=severity,
        acknowledged=acknowledged,
        extension_version="0.1.0-test",
    )
    for key, value in overrides.items():
        setattr(obs, key, value)
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return obs


# ── Extension tokens ────────────────────────────────────────────────────


def make_extension_token(
    db: Session,
    org: Organization,
    plaintext: str | None = None,
) -> tuple[ClinicExtensionToken, str]:
    """Persist a hashed extension token; returns (row, plaintext)."""
    token_plain = plaintext or _short("ext_token_")
    token = ClinicExtensionToken(
        id=_short("etok_"),
        org_id=org.id,
        token_hash=hashlib.sha256(token_plain.encode("utf-8")).hexdigest(),
        issued_at=datetime.utcnow(),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, token_plain


# ── Billing events ──────────────────────────────────────────────────────


def make_billing_event(
    db: Session,
    org: Organization | None,
    *,
    event_type: str = "checkout.session.completed",
    stripe_event_id: str | None = None,
    payload: dict[str, Any] | None = None,
    status: str = "processed",
) -> BillingEvent:
    evt = BillingEvent(
        id=_short("be_"),
        org_id=org.id if org is not None else None,
        stripe_event_id=stripe_event_id or f"evt_test_{_short()}",
        event_type=event_type,
        payload=payload or {},
        processed_at=datetime.utcnow(),
        status=status,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    return evt


# ── Report artifacts ────────────────────────────────────────────────────


def make_report_artifact(
    db: Session,
    org: Organization,
    *,
    storage_uri: str | None = None,
    status: str = "ready",
) -> ClinicReportArtifact:
    art = ClinicReportArtifact(
        id=_short("rep_"),
        org_id=org.id,
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        storage_uri=storage_uri or "file:///tmp/clinic-report-test.pdf",
        size_bytes=1024,
        generated_at=datetime.utcnow(),
        status=status,
    )
    db.add(art)
    db.commit()
    db.refresh(art)
    return art


__all__ = [
    "make_clinic_org",
    "make_clinic_admin",
    "make_clinic_tool",
    "make_clinic_observation",
    "make_extension_token",
    "make_billing_event",
    "make_report_artifact",
]
