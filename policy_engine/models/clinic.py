"""Clinic-tier domain models.

These tables are exclusive to the clinic SaaS persona (`Organization.tier`
in {clinic_basic, clinic_standard, clinic_multi_site}) and are never read by
enterprise routes.  Keeping them in a dedicated module preserves the
"existing tenants unchanged" invariant.

* ``ClinicAiTool``      — manually registered AI tools (lightweight model_card)
* ``ClinicAiObservation`` — DNS / page-context detections from the clinic-lite
  browser extension (deliberately segregated from the hospital
  ``shadow_ai_detections`` table; the hospital network detector path stays
  untouched).
* ``BillingEvent``      — Stripe webhook audit trail.  Schema is forward-
  compatible with ``BILLING_IMPLEMENTATION.md`` — when the full billing
  system lands, this is the same row shape.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, DateTime, Boolean, JSON, ForeignKey, Integer, Index, Enum,
)

from policy_engine.database import Base


class ClinicAiToolStatus(str, enum.Enum):
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    RETIRED = "retired"


class ClinicAiToolRisk(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClinicAiToolCategory(str, enum.Enum):
    AMBIENT_SCRIBE = "ambient_scribe"
    DOCUMENTATION = "documentation"
    DECISION_SUPPORT = "decision_support"
    IMAGING = "imaging"
    PATIENT_COMMUNICATION = "patient_communication"
    REVENUE_CYCLE = "revenue_cycle"
    OTHER = "other"


class ClinicAiToolModelTrainingStatus(str, enum.Enum):
    """Vendor's capability — does the tool train its models on customer prompts?

    Distinct from ``ClinicAiToolPracticeOptOutState`` (HEALTH-5 split): this
    column records what the vendor *offers*, not what the practice has
    *configured*. See PRD.v2.md §6.8.2.a.
    """

    UNKNOWN = "unknown"
    NO_TRAINING = "no_training"
    TRAINS_ON_CUSTOMER_DATA = "trains_on_customer_data"
    OPT_OUT_AVAILABLE = "opt_out_available"


class ClinicAiToolPracticeOptOutState(str, enum.Enum):
    """The practice's actual configuration of the vendor opt-out.

    Audit-relevant — answers the compliance officer's question "is opt-out
    actually toggled in our ChatGPT Team account today?" Only ``Admin``
    product-role users may transition to ``VERIFIED``; see
    ``policy_engine/routes/clinic/tools.py``.
    """

    NOT_APPLICABLE = "not_applicable"
    REQUIRED_NOT_SET = "required_not_set"
    REQUIRED_AND_SET = "required_and_set"
    VERIFIED = "verified"


class ClinicAiTool(Base):
    """An AI tool a clinic has manually registered.

    Conceptually a stripped-down ``ModelCard`` — no bias audit, no drift
    monitor, no MLflow artefacts.  Just the things a single-clinic owner
    actually knows: vendor, what it does, how risky it feels, who is
    responsible.
    """
    __tablename__ = "clinic_ai_tools"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    vendor = Column(String, nullable=True)
    category = Column(
        Enum(ClinicAiToolCategory),
        nullable=False,
        default=ClinicAiToolCategory.OTHER,
    )
    purpose = Column(String, nullable=True)
    handles_phi = Column(Boolean, nullable=False, default=False)
    risk_level = Column(
        Enum(ClinicAiToolRisk),
        nullable=False,
        default=ClinicAiToolRisk.LOW,
    )
    status = Column(
        Enum(ClinicAiToolStatus),
        nullable=False,
        default=ClinicAiToolStatus.ACTIVE,
    )
    owner_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes = Column(String, nullable=True)
    source = Column(String, nullable=False, default="manual")  # manual | extension
    # PRD.v2.md §6.8.2.a — model training status (vendor capability) and
    # practice opt-out state (practice configuration). HEALTH-5 split.
    model_training_status = Column(
        Enum(ClinicAiToolModelTrainingStatus),
        nullable=False,
        default=ClinicAiToolModelTrainingStatus.UNKNOWN,
    )
    practice_opt_out_state = Column(
        Enum(ClinicAiToolPracticeOptOutState),
        nullable=False,
        default=ClinicAiToolPracticeOptOutState.NOT_APPLICABLE,
    )
    opt_out_verified_at = Column(DateTime, nullable=True)
    opt_out_verified_by_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_training_status_evidence = Column(String(2000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ClinicAiObservation(Base):
    """Browser-extension + DNS-only detections (Shadow AI Lite).

    Deliberately kept separate from the hospital-grade
    ``shadow_ai_detections`` table so the existing detector pipeline is
    undisturbed.  ``host`` is the DNS hostname; ``tool_fingerprint`` is the
    extension's heuristic match (e.g., "chatgpt", "claude_web").  No PHI is
    transmitted — only host names and tool fingerprints.
    """
    __tablename__ = "clinic_ai_observations"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    host = Column(String, nullable=False)
    tool_fingerprint = Column(String, nullable=True)
    page_url_hash = Column(String, nullable=True)  # SHA-256, never the URL itself
    severity = Column(String, nullable=False, default="low")
    observed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    user_agent = Column(String, nullable=True)
    extension_version = Column(String, nullable=True)
    acknowledged = Column(Boolean, nullable=False, default=False)


Index(
    "ix_clinic_obs_org_observed",
    ClinicAiObservation.org_id,
    ClinicAiObservation.observed_at.desc(),
)


class BillingEvent(Base):
    """Stripe webhook audit trail.

    Idempotency key is ``stripe_event_id`` — every handler checks here
    first.  ``payload`` stores the full webhook body so support can replay
    the timeline.  Schema is forward-compatible with
    ``BILLING_IMPLEMENTATION.md`` §3.2.
    """
    __tablename__ = "billing_events"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stripe_event_id = Column(String, unique=True, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String, nullable=False, default="processed")  # processed | failed | skipped
    error_message = Column(String, nullable=True)


class ClinicExtensionToken(Base):
    """Hashed bearer token issued to a clinic's browser extension.

    Plaintext is shown to the user *once* at issuance; we persist only
    a SHA-256 hash so a DB read does not leak active tokens.  Lookup is
    O(1) via the unique hash index — see migration 017.
    """
    __tablename__ = "clinic_extension_tokens"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    token_hash = Column(String, nullable=False, unique=True, index=True)
    issued_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    issued_by_user_id = Column(String, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)


class ClinicReportArtifact(Base):
    """Pointer to a generated monthly clinic compliance PDF.

    The PDF itself lives in ``STORAGE_BACKEND`` (object storage in prod,
    local FS in dev).  This row tracks generation status and gives the
    dashboard something to render in the "Download latest report" card.
    """
    __tablename__ = "clinic_report_artifacts"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    storage_uri = Column(String, nullable=False)  # e.g., s3://... or file://...
    size_bytes = Column(Integer, nullable=True)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String, nullable=False, default="ready")  # ready | failed | generating
    error_message = Column(String, nullable=True)


Index(
    "ix_clinic_report_org_period",
    ClinicReportArtifact.org_id,
    ClinicReportArtifact.period_end.desc(),
)
