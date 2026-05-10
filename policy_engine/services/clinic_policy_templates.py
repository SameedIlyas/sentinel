"""Preset library of clinic-friendly policy templates.

Each template is a recipe for a real ``Policy`` row.  Apply-time
materialization happens in ``policy_engine/routes/clinic/policy_templates``.

Design notes:

* Same ``Policy`` schema as the enterprise tier — no parallel policy table.
* ``applies_to=['*']`` by default so a clinic with one tool gets coverage
  immediately; the user can scope down later.
* Template language is plain English; the technical fields underneath stay
  identical to enterprise policies so existing evaluation pipelines keep
  working.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class PolicyTemplate:
    template_id: str
    name: str  # short, clinic-friendly label
    description: str  # plain-English explanation
    why_it_matters: str  # one sentence on the risk it addresses
    policy_type: str
    rules: list[dict[str, Any]] = field(default_factory=list)
    applies_to: list[str] = field(default_factory=lambda: ["*"])
    priority: int = 100
    enabled: bool = True
    recommended_for_tiers: tuple[str, ...] = (
        "clinic_basic",
        "clinic_standard",
        "clinic_multi_site",
    )

    def to_policy_dict(self) -> dict[str, Any]:
        out = asdict(self)
        # Strip presentation-only fields before handing to the policy creator.
        for key in ("template_id", "why_it_matters", "recommended_for_tiers"):
            out.pop(key, None)
        return out


CLINIC_POLICY_TEMPLATES: tuple[PolicyTemplate, ...] = (
    PolicyTemplate(
        template_id="block_phi_to_public_llm",
        name="Block patient info from going to public AI tools",
        description=(
            "Stops staff from accidentally pasting patient names, dates of "
            "birth, MRNs, or other identifiers into public AI tools like "
            "ChatGPT or Claude.ai."
        ),
        why_it_matters=(
            "Public LLMs are not HIPAA-covered. This is the #1 way clinics "
            "land in a breach notification."
        ),
        policy_type="data_protection",
        rules=[
            {
                "description": "Block when PHI is present and destination is public LLM",
                "conditions": [
                    {"field": "data_touched", "operator": "contains", "value": "phi"},
                    {
                        "field": "system_accessed",
                        "operator": "in",
                        "value": [
                            "openai_public",
                            "anthropic_public",
                            "google_gemini_public",
                            "perplexity",
                        ],
                    },
                ],
                "action": "block",
            }
        ],
        priority=1000,
    ),
    PolicyTemplate(
        template_id="require_review_clinical_decision",
        name="Require human review for clinical decisions",
        description=(
            "When an AI tool recommends a diagnosis, a treatment, or a "
            "denial of care, a clinician has to confirm it before action."
        ),
        why_it_matters=(
            "Clinical autonomy is a regulatory expectation. Auto-actioned "
            "AI decisions are a malpractice exposure."
        ),
        policy_type="access_control",
        rules=[
            {
                "description": "Require human review for clinical-decision tools",
                "conditions": [
                    {
                        "field": "tool_name",
                        "operator": "contains",
                        "value": "clinical",
                    },
                ],
                "action": "require_approval",
            }
        ],
        priority=900,
    ),
    PolicyTemplate(
        template_id="mask_phi_in_logs",
        name="Mask patient info in logs",
        description=(
            "When the platform records what an AI tool did, patient names "
            "and MRNs are replaced with placeholders. Audit usefulness "
            "stays; PHI exposure shrinks."
        ),
        why_it_matters=(
            "Even your own audit logs are a breach surface if they store "
            "raw PHI."
        ),
        policy_type="data_protection",
        rules=[
            {
                "description": "Mask PHI fields before write",
                "conditions": [
                    {"field": "data_touched", "operator": "contains", "value": "phi"},
                ],
                "action": "mask",
                "parameters": {"mask_fields": ["patient_name", "mrn", "dob", "ssn"]},
            }
        ],
        priority=800,
    ),
    PolicyTemplate(
        template_id="block_after_hours_high_risk",
        name="Block high-risk AI actions outside clinic hours",
        description=(
            "Outside 7am–7pm, AI tools cannot make high-risk decisions "
            "(orders, prior auth submissions, refunds) without a live "
            "clinician on call."
        ),
        why_it_matters=(
            "Most AI safety incidents happen when no one is watching."
        ),
        policy_type="access_control",
        rules=[
            {
                "description": "Block high-risk actions outside business hours",
                "conditions": [
                    {
                        "field": "tool_name",
                        "operator": "in",
                        "value": ["place_order", "submit_prior_auth", "issue_refund"],
                    },
                    {
                        "field": "context.business_hours",
                        "operator": "eq",
                        "value": False,
                    },
                ],
                "action": "block",
            }
        ],
        priority=700,
        recommended_for_tiers=("clinic_standard", "clinic_multi_site"),
    ),
    PolicyTemplate(
        template_id="alert_new_ai_tool",
        name="Alert when an unknown AI tool starts reporting",
        description=(
            "If a new AI tool not in your registry starts sending data, "
            "raise an alert so you can decide whether to register it or "
            "block it."
        ),
        why_it_matters=(
            "Shadow IT in clinics is mostly accidental — but it's still "
            "shadow IT."
        ),
        policy_type="access_control",
        rules=[
            {
                "description": "Alert on unregistered tool",
                "conditions": [
                    {
                        "field": "context.tool_registered",
                        "operator": "eq",
                        "value": False,
                    },
                ],
                "action": "require_approval",
            }
        ],
        priority=600,
    ),
    PolicyTemplate(
        template_id="prior_auth_audit_trail",
        name="Record every prior-auth AI decision",
        description=(
            "Every time an AI helps decide a prior authorization, the "
            "decision and the model's reasoning are written to an audit "
            "log a payer can subpoena."
        ),
        why_it_matters=(
            "Prior-auth disputes lose without a clear AI trail. Win them "
            "with one."
        ),
        policy_type="financial",
        rules=[
            {
                "description": "Audit prior-auth decisions",
                "conditions": [
                    {
                        "field": "tool_name",
                        "operator": "contains",
                        "value": "prior_auth",
                    },
                ],
                "action": "allow",
                "parameters": {"audit_level": "verbose"},
            }
        ],
        priority=500,
        recommended_for_tiers=("clinic_standard", "clinic_multi_site"),
    ),
    PolicyTemplate(
        template_id="block_billing_code_changes_by_ai",
        name="Don't let AI tools change billing codes alone",
        description=(
            "AI can suggest billing code changes; a human in your billing "
            "team has to confirm before they go to the payer."
        ),
        why_it_matters=(
            "Up-coding by AI is one of the fastest ways to attract a "
            "False Claims Act audit."
        ),
        policy_type="financial",
        rules=[
            {
                "description": "Require approval before AI changes billing codes",
                "conditions": [
                    {
                        "field": "tool_name",
                        "operator": "contains",
                        "value": "billing",
                    },
                    {
                        "field": "arguments.action",
                        "operator": "in",
                        "value": ["change_code", "upgrade_code"],
                    },
                ],
                "action": "require_approval",
            }
        ],
        priority=550,
        recommended_for_tiers=("clinic_standard", "clinic_multi_site"),
    ),
)


def list_templates_for_tier(tier: str) -> list[PolicyTemplate]:
    return [t for t in CLINIC_POLICY_TEMPLATES if tier in t.recommended_for_tiers]


def get_template(template_id: str) -> PolicyTemplate | None:
    for t in CLINIC_POLICY_TEMPLATES:
        if t.template_id == template_id:
            return t
    return None
