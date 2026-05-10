"""Shadow AI Lite — endpoints for the browser extension.

The extension reports DNS lookups and tool fingerprints (no PHI).

Token storage: the per-org extension token is hashed (SHA-256) into the
``clinic_extension_tokens`` table.  Plaintext is shown to the user
*once* on issuance.  Subsequent dashboard loads see a "rotate" affordance
only — losing the token requires generating a new one.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.models.clinic import ClinicAiObservation, ClinicExtensionToken
from policy_engine.models.organization import Organization
from policy_engine.models.user import User
from policy_engine.services.clinic_audit import write_clinic_audit
from policy_engine.services.tier_filter import (
    require_clinic_tier,
    require_clinic_tier_with_baa,
)

router = APIRouter()


def _hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


# ── Per-org extension token ─────────────────────────────────────────────

class ExtensionTokenStatus(BaseModel):
    has_active_token: bool
    issued_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


class ExtensionTokenIssued(BaseModel):
    token: str  # plaintext — shown ONCE
    install_url: str
    issued_at: datetime
    warning: str


@router.get("/shadow-ai/extension-token/status", response_model=ExtensionTokenStatus)
def token_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    row = (
        db.query(ClinicExtensionToken)
        .filter(
            ClinicExtensionToken.org_id == org.id,
            ClinicExtensionToken.revoked_at.is_(None),
        )
        .first()
    )
    if not row:
        return ExtensionTokenStatus(has_active_token=False)
    return ExtensionTokenStatus(
        has_active_token=True,
        issued_at=row.issued_at,
        last_used_at=row.last_used_at,
    )


@router.post("/shadow-ai/extension-token", response_model=ExtensionTokenIssued)
def issue_token(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    """Issue (or rotate) the extension token.

    Plaintext is returned in the response and never persisted.  Existing
    active tokens are revoked first so a stolen token cannot keep
    pushing observations alongside the rotated one.
    """
    now = datetime.utcnow()
    # Revoke any existing active token for this org.
    existing = (
        db.query(ClinicExtensionToken)
        .filter(
            ClinicExtensionToken.org_id == org.id,
            ClinicExtensionToken.revoked_at.is_(None),
        )
        .all()
    )
    for row in existing:
        row.revoked_at = now

    plaintext = secrets.token_urlsafe(32)
    db.add(
        ClinicExtensionToken(
            id=str(uuid.uuid4()),
            org_id=org.id,
            token_hash=_hash_token(plaintext),
            issued_at=now,
            issued_by_user_id=current_user.id,
        )
    )
    write_clinic_audit(
        db,
        user=current_user,
        org_id=org.id,
        action="clinic.extension.token_issued",
        system="clinic.shadow_ai",
        data_touched=[org.id],
        reason="Extension token issued/rotated",
    )
    db.commit()
    return ExtensionTokenIssued(
        token=plaintext,
        install_url="/clinic/extension/install",
        issued_at=now,
        warning=(
            "Save this token now — for security we never display it again. "
            "If you lose it, rotate to issue a new one."
        ),
    )


# ── Observation ingest (extension-side) ─────────────────────────────────

class ObservationCreate(BaseModel):
    host: str = Field(..., min_length=1, max_length=255)
    tool_fingerprint: Optional[str] = Field(None, max_length=120)
    page_url_hash: Optional[str] = Field(None, max_length=128)
    severity: str = Field("low", pattern="^(low|medium|high|critical)$")
    user_agent: Optional[str] = Field(None, max_length=500)
    extension_version: Optional[str] = Field(None, max_length=40)


@router.post(
    "/shadow-ai/observations",
    status_code=status.HTTP_202_ACCEPTED,
)
def post_observation(
    payload: ObservationCreate,
    db: Session = Depends(get_db),
    x_clinic_extension_token: Optional[str] = Header(None),
):
    """Extension-side ingest.

    Auth: the per-org extension token issued via the wizard.  Verified
    against the hashed-token table — O(1) index lookup, no plaintext
    DB read.  BAA must be signed; otherwise we refuse the observation
    so the platform never accepts PHI-adjacent data without a BAA in
    force (HIPAA §164.502(e)).
    """
    if not x_clinic_extension_token:
        raise HTTPException(status_code=401, detail="Missing extension token")

    token_hash = _hash_token(x_clinic_extension_token)
    row = (
        db.query(ClinicExtensionToken)
        .filter(
            ClinicExtensionToken.token_hash == token_hash,
            ClinicExtensionToken.revoked_at.is_(None),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid extension token")

    org = db.query(Organization).filter(Organization.id == row.org_id).first()
    if (
        org is None
        or not org.is_active
        or org.tier not in ("clinic_basic", "clinic_standard", "clinic_multi_site")
    ):
        raise HTTPException(status_code=401, detail="Invalid extension token")

    if not org.hipaa_baa_signed:
        # HIPAA: we cannot ingest practice telemetry before the BAA is
        # signed.  The dashboard surfaces this so the practice owner can
        # finish onboarding first.
        raise HTTPException(
            status_code=409,
            detail={
                "error": "baa_required",
                "message": (
                    "Your practice has not signed its BAA yet — "
                    "observations cannot be accepted until that's done."
                ),
            },
        )

    # Trim user_agent down to a coarse fingerprint to honour data
    # minimisation (GDPR Art. 5(c)).  We still keep something useful for
    # support but drop the long detail string.
    coarse_ua = (payload.user_agent or "").strip()[:120] or None

    obs = ClinicAiObservation(
        id=str(uuid.uuid4()),
        org_id=org.id,
        host=payload.host[:255],
        tool_fingerprint=payload.tool_fingerprint,
        page_url_hash=payload.page_url_hash,
        severity=payload.severity,
        observed_at=datetime.utcnow(),
        user_agent=coarse_ua,
        extension_version=payload.extension_version,
        acknowledged=False,
    )
    db.add(obs)
    row.last_used_at = datetime.utcnow()
    db.commit()
    return {"status": "accepted"}


# ── Dashboard read-side ─────────────────────────────────────────────────

class ObservationResponse(BaseModel):
    id: str
    host: str
    tool_fingerprint: Optional[str]
    severity: str
    observed_at: datetime
    extension_version: Optional[str]
    acknowledged: bool

    class Config:
        from_attributes = True


@router.get("/shadow-ai/observations", response_model=list[ObservationResponse])
def list_observations(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    rows = (
        db.query(ClinicAiObservation)
        .filter(ClinicAiObservation.org_id == org.id)
        .order_by(ClinicAiObservation.observed_at.desc())
        .limit(min(limit, 500))
        .all()
    )
    return rows


@router.post("/shadow-ai/observations/{obs_id}/acknowledge")
def acknowledge(
    obs_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    row = (
        db.query(ClinicAiObservation)
        .filter(
            ClinicAiObservation.id == obs_id,
            ClinicAiObservation.org_id == org.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Observation not found")
    row.acknowledged = True
    db.commit()
    return {"status": "ok"}
