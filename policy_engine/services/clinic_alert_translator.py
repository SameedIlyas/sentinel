"""Plain-English alert translator for clinic-tier orgs.

Hospital alerts use technical language ("policy_evaluation rejected with
constraint X").  Clinics need the same signal in office-manager language
("Action blocked: a tool tried to share patient information").  The
translator runs at *render* time — alert rows in the database keep their
canonical wording so enterprise consumers are unaffected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from policy_engine.models.organization import is_clinic_tier


# ── Static translation table ────────────────────────────────────────────
# Keys are alert_type strings (free-form today); we match by `alert_type`
# first, then fall back to a regex sweep over the description.

_ALERT_TYPE_TRANSLATIONS: dict[str, tuple[str, str]] = {
    # alert_type → (clinic_title, clinic_template)
    "blocked_access": (
        "Action blocked",
        "An AI tool tried to access {{system}} and was blocked. No patient "
        "information was shared.",
    ),
    "phi_in_prompt": (
        "Patient info caught in a prompt",
        "A staff member tried to send patient information to {{tool}}. The "
        "platform stopped this before any data left your network.",
    ),
    "shadow_ai_detected": (
        "Unsanctioned AI tool spotted",
        "Someone in your practice was using {{tool}} on a work device. Add it "
        "to your registry, or block it if it's not approved.",
    ),
    "high_transaction": (
        "High-value AI decision flagged",
        "An AI-assisted decision crossed your review threshold. Open the "
        "review queue to confirm or override.",
    ),
    "drift_warning": (
        "AI tool acting differently",
        "{{tool}}'s behavior has shifted. Have someone review its recent "
        "decisions before relying on it again.",
    ),
    "drift_alert": (
        "AI tool needs urgent review",
        "{{tool}} is no longer behaving the way it did when you onboarded "
        "it. Pause its use until a clinician confirms it's safe.",
    ),
    "bias_finding": (
        "Fairness concern in an AI tool",
        "A fairness check on {{tool}} flagged unequal performance across "
        "patient groups. Review before continuing to use it for decisions.",
    ),
    "new_agent": (
        "New AI tool started reporting",
        "A new AI tool ({{tool}}) just connected. If you didn't expect this, "
        "investigate who installed it.",
    ),
    "policy_violation": (
        "Practice rule was broken",
        "{{tool}} did something that violates one of your practice rules.",
    ),
}


# Regex patterns over the description text — used when alert_type is
# missing or generic.
_DESCRIPTION_RULES: tuple[tuple[re.Pattern[str], tuple[str, str]], ...] = (
    (
        re.compile(r"phi|protected health information", re.IGNORECASE),
        (
            "Patient info caught in a prompt",
            "Patient information was about to be sent outside your practice. "
            "We stopped it.",
        ),
    ),
    (
        re.compile(r"\bblock(ed)?\b", re.IGNORECASE),
        (
            "Action blocked",
            "An AI tool was blocked from doing something risky. No data was "
            "shared.",
        ),
    ),
    (
        re.compile(r"\bdrift\b", re.IGNORECASE),
        (
            "AI tool acting differently",
            "An AI tool's behavior has shifted from when you onboarded it.",
        ),
    ),
)


_NEXT_STEPS: dict[str, str] = {
    "blocked_access": "Review the audit log to confirm nothing slipped through.",
    "phi_in_prompt": "Talk to the staff member and update your training notes.",
    "shadow_ai_detected": "Decide: register the tool, or block it for everyone.",
    "high_transaction": "Open the review queue and decide on the flagged item.",
    "drift_warning": "Schedule a review with whoever owns this tool.",
    "drift_alert": "Pause the tool until a clinician reviews it.",
    "bias_finding": "Review the fairness report before continuing to use the tool.",
    "new_agent": "Confirm with IT that this tool is expected.",
    "policy_violation": "Check whether the rule should be updated, or talk to the user.",
}


@dataclass(frozen=True)
class TranslatedAlert:
    title: str
    description: str
    next_step: str | None
    severity_label: str
    is_translated: bool


_SEVERITY_LABELS = {
    "low": "Low — informational",
    "medium": "Medium — review when you can",
    "high": "High — review today",
    "critical": "Critical — review now",
}


def _format_template(template: str, **subs: str) -> str:
    out = template
    for key, value in subs.items():
        out = out.replace("{{" + key + "}}", value)
    # Strip any unsubstituted placeholders so we never show "{{tool}}" in the UI.
    out = re.sub(r"\{\{\s*\w+\s*\}\}", "this AI tool", out)
    return out


def translate_alert(
    *,
    tier: str | None,
    alert_type: str | None,
    severity: str | None,
    description: str | None,
    tool_name: str | None = None,
    system_name: str | None = None,
) -> TranslatedAlert:
    """Translate an alert for the given tier.

    Enterprise tier returns the canonical wording (no translation).  Clinic
    tiers get a clinic-friendly title + description + suggested next step.

    The function is pure — no DB access — so it is cheap to call on every
    alert read and easy to unit-test.
    """
    severity_label = _SEVERITY_LABELS.get((severity or "").lower(), severity or "Info")

    if not is_clinic_tier(tier):
        return TranslatedAlert(
            title=alert_type or "Alert",
            description=description or "",
            next_step=None,
            severity_label=severity_label,
            is_translated=False,
        )

    subs = {
        "tool": tool_name or "an AI tool",
        "system": system_name or "a connected system",
    }

    if alert_type and alert_type in _ALERT_TYPE_TRANSLATIONS:
        title, template = _ALERT_TYPE_TRANSLATIONS[alert_type]
        return TranslatedAlert(
            title=title,
            description=_format_template(template, **subs),
            next_step=_NEXT_STEPS.get(alert_type),
            severity_label=severity_label,
            is_translated=True,
        )

    # Fallback — pattern match the description.
    if description:
        for pattern, (title, template) in _DESCRIPTION_RULES:
            if pattern.search(description):
                return TranslatedAlert(
                    title=title,
                    description=_format_template(template, **subs),
                    next_step=None,
                    severity_label=severity_label,
                    is_translated=True,
                )

    # Last-resort: keep canonical text but add severity phrasing so the UI
    # never shows blank.  Better to be safe than to swallow an alert.
    return TranslatedAlert(
        title=alert_type or "Alert",
        description=description or "An AI tool triggered an alert in your practice.",
        next_step="Open the alert in the audit log for full details.",
        severity_label=severity_label,
        is_translated=False,
    )
