"""Extended demo seeder — fattens every table so pagination, filters,
charts, and cross-page links all light up with realistic-looking data.

Designed to run AFTER `seed_demo_data.py` and `seed_demo_healthcare.py`.

Adds:
  - 25 audit logs per agent (variety of decisions, tools, departments)
  - 18 alerts of varying severity, half acknowledged
  - 30+ shadow-AI detections covering every provider in the host list
  - 18 scribe audits (some hallucinations, some clean)
  - 22 prior-auth records (chained hash) covering approve/deny/pending
  - 25 revenue-cycle audits (with findings: upcoding/unbundling/modifier)
  - 18 adverse events (severities and statuses)
  - 12 PMS reports (quarterly + annual, draft + published)
  - 30 risk-score history points across 6 models (uptrend / downtrend)
  - 18 HITL reviews (every priority, every status)
  - 12 transparency records (mix of published + draft)
  - 30 drift measurements with PSI / KS time series + 8 alerts
  - 15 bias-audit results across 4 audits, including failing subgroups
  - 8 technical files (510(k) + EU MDR mix, with sections)

Idempotent: skips a table if it already has more rows than the target.

Usage:
    alembic upgrade head
    python create_admin_user.py --default
    python seed_demo_data.py
    python seed_demo_healthcare.py
    python seed_demo_extended.py            # <-- this script
"""
from __future__ import annotations

import hashlib
import random
import sys
import uuid
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

sys.path.insert(0, ".")

from policy_engine.database import SessionLocal  # noqa: E402
from policy_engine.models.agent import Agent  # noqa: E402
from policy_engine.models.alert import Alert, AlertSeverity  # noqa: E402
from policy_engine.models.audit_log import AuditLog  # noqa: E402
from policy_engine.models.bias_audit import (  # noqa: E402
    BiasAuditModel, BiasAuditResultModel, BiasAuditSubgroup,
)
from policy_engine.models.drift import (  # noqa: E402
    DriftAlert, DriftBaseline, DriftMeasurementModel,
)
from policy_engine.models.hitl import HITLAuditTrail, HITLReview  # noqa: E402
from policy_engine.models.model_card import ModelCard  # noqa: E402
from policy_engine.models.policy import Policy  # noqa: E402
from policy_engine.models.post_market import (  # noqa: E402
    AdverseEvent, AdverseEventSeverityDB, AdverseEventStatusDB,
    PMSMetric, PMSReport, PMSReportStatusDB, PMSReportTypeDB,
)
from policy_engine.models.prior_auth import PriorAuthRecord  # noqa: E402
from policy_engine.models.revenue_cycle import (  # noqa: E402
    RevenueCycleAudit, RevenueCycleFinding,
)
from policy_engine.models.risk_score import (  # noqa: E402
    RiskScore, RiskScoreHistory,
)
from policy_engine.models.scribe_audit import (  # noqa: E402
    ScribeAuditFinding, ScribeAuditModel,
)
from policy_engine.models.shadow_ai import ShadowAIDetectionModel  # noqa: E402
from policy_engine.models.technical_file import (  # noqa: E402
    RegulatoryTypeDB, TechnicalFile, TechnicalFileLifecycleDB,
    TechnicalFileSection,
)
from policy_engine.models.transparency import (  # noqa: E402
    TransparencyAcknowledgment, TransparencyRecordModel, TransparencyVersion,
)
from policy_engine.models.user import User, UserRole  # noqa: E402

random.seed(42)
NOW = datetime.utcnow()


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────

def uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def days_ago(d: int) -> datetime:
    return NOW - timedelta(days=d, hours=random.randint(0, 23), minutes=random.randint(0, 59))


def hours_ago(h: int) -> datetime:
    return NOW - timedelta(hours=h, minutes=random.randint(0, 59))


def admin_id(db) -> str:
    u = db.query(User).filter(User.role.in_([UserRole.ORG_ADMIN, UserRole.SYSTEM_ADMIN])).first()
    return u.id if u else "user_system"


def first_org_id(db) -> Optional[str]:
    u = db.query(User).first()
    return u.organization_id if u else None


def has_at_least(db, model, n: int) -> bool:
    return db.query(model).count() >= n


def safe_pick(items: Iterable, default=None):
    items = list(items)
    return random.choice(items) if items else default


# ───────────────────────────────────────────────────────────────────────────
# Audit logs — variety of decisions across agents and tools
# ───────────────────────────────────────────────────────────────────────────

AUDIT_TOOLS = [
    ("query_database",    "ehr",        ["patient_record"], "access_control"),
    ("send_email",        "email",      ["external"],       "data_protection"),
    ("transfer_funds",    "ledger",     ["account"],        "financial"),
    ("read_lab_results",  "lis",        ["lab_panel"],      "access_control"),
    ("export_data",       "warehouse",  ["dataset"],        "data_protection"),
    ("create_purchase_order","erp",     ["po"],             "financial"),
    ("update_schedule",   "calendar",   ["appointment"],    "access_control"),
    ("post_message",      "slack",      ["channel"],        "data_protection"),
    ("call_external_api", "internet",   ["api"],            "access_control"),
    ("modify_policy",     "policy_engine", ["policy"],      "access_control"),
]

DECISIONS = [
    ("allowed",           0.62),
    ("blocked",           0.18),
    ("requires_approval", 0.13),
    ("masked",            0.07),
]


def weighted(choices):
    r = random.random()
    cum = 0.0
    for value, weight in choices:
        cum += weight
        if r <= cum:
            return value
    return choices[-1][0]


def seed_audit_logs(db, target: int = 240) -> int:
    if has_at_least(db, AuditLog, target):
        print(f"    audit_logs: already >= {target}, skipping")
        return 0
    agents = db.query(Agent).all()
    if not agents:
        print("    audit_logs: no agents, skipping")
        return 0
    org_id = first_org_id(db)
    created = 0
    for _ in range(target):
        agent = random.choice(agents)
        tool, system, data, _ptype = random.choice(AUDIT_TOOLS)
        decision = weighted(DECISIONS)
        ts = hours_ago(random.randint(1, 24 * 30))
        db.add(AuditLog(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            agent_name=agent.name or agent.id,
            user_id=f"user_{random.randint(1, 12):03d}",
            tool_name=tool,
            arguments={"target_id": uid("rec_"), "amount": random.randint(50, 9_500)} if tool == "transfer_funds" else {"target_id": uid("rec_")},
            system_accessed=system,
            data_touched=data,
            decision=decision,
            policy_ids=[],
            reason={
                "allowed": "Within policy",
                "blocked": "Out of approved scope",
                "requires_approval": "Threshold exceeded; awaiting review",
                "masked": "PHI detected; output redacted",
            }[decision],
            log_metadata={"department": random.choice(["icu", "ed", "or", "radiology", "billing", "admin"])},
            timestamp=ts,
        ))
        created += 1
    db.commit()
    print(f"    audit_logs: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Alerts — variety of severities + ack states
# ───────────────────────────────────────────────────────────────────────────

ALERT_TEMPLATES = [
    ("blocked_access",            AlertSeverity.HIGH,     "Agent attempted to access patient records outside approved scope"),
    ("high_transaction",          AlertSeverity.HIGH,     "Transfer of $8,400 blocked — exceeds tier-2 limit"),
    ("data_protection_violation", AlertSeverity.CRITICAL, "PHI detected in outbound API call to non-allowlisted host"),
    ("approval_required",         AlertSeverity.MEDIUM,   "Tool call requires CFO sign-off"),
    ("new_agent",                 AlertSeverity.MEDIUM,   "New agent auto-registered: needs governance review"),
    ("rate_limit_breach",         AlertSeverity.MEDIUM,   "Agent exceeded 100 calls/min for 3 minutes"),
    ("policy_violation",          AlertSeverity.HIGH,     "Tool call violates HIPAA minimum-necessary rule"),
    ("phi_redaction_failed",      AlertSeverity.CRITICAL, "PHI redaction engine returned 0 findings on a known-PHI payload"),
    ("drift_alert",               AlertSeverity.HIGH,     "PSI = 0.31 on age feature — significant drift detected"),
    ("failed_login",              AlertSeverity.LOW,      "Repeated failed login attempts from unfamiliar IP"),
]


def seed_alerts(db, target: int = 40) -> int:
    if has_at_least(db, Alert, target):
        print(f"    alerts: already >= {target}, skipping")
        return 0
    admin = admin_id(db)
    agents = db.query(Agent).all()
    created = 0
    needed = target - db.query(Alert).count()
    for _ in range(max(0, needed)):
        alert_type, severity, desc = random.choice(ALERT_TEMPLATES)
        agent = random.choice(agents) if agents else None
        ts = hours_ago(random.randint(1, 24 * 14))
        ack = random.random() < 0.45
        db.add(Alert(
            id=str(uuid.uuid4()),
            timestamp=ts,
            severity=severity,
            alert_type=alert_type,
            agent_id=agent.id if agent else "agent_system",
            description=desc,
            audit_log_id=None,
            acknowledged=ack,
            acknowledged_by=admin if ack else None,
            acknowledged_at=ts + timedelta(minutes=random.randint(5, 360)) if ack else None,
        ))
        created += 1
    db.commit()
    print(f"    alerts: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Shadow AI — broad coverage of providers, departments, PHI risk
# ───────────────────────────────────────────────────────────────────────────

SHADOW_AI_DETECTIONS = [
    # (host, provider, dept, port, phi_risk, status, notes)
    ("api.openai.com",                  "openai",        "ICU",         443, "high",   "detected",       "1.2 MB POST in business hours; clinician dept"),
    ("chat.openai.com",                 "openai",        "Cardiology",  443, "high",   "investigating",  "Browser session — possible patient note pasting"),
    ("api.anthropic.com",               "anthropic",     "Radiology",   443, "high",   "detected",       "Repeated POSTs; check for image-of-PHI uploads"),
    ("claude.ai",                       "anthropic",     "Pharmacy",    443, "high",   "approved",       "Clinical pharmacist using Claude for literature review"),
    ("api.mistral.ai",                  "mistral",       "Engineering", 443, "low",    "detected",       "Backend service — likely test code"),
    ("api.cohere.com",                  "cohere",        "Marketing",   443, "low",    "approved",       "Marketing team approved use case"),
    ("api.deepseek.com",                "deepseek",      "Research",    443, "medium", "detected",       "Researcher experimenting with reasoning model"),
    ("api.groq.com",                    "groq",          "ED",          443, "high",   "blocked",        "Blocked at gateway — clinical dept, unapproved provider"),
    ("api.perplexity.ai",               "perplexity",    "Operations",  443, "low",    "approved",       "Ops team using for vendor research"),
    ("openrouter.ai",                   "openrouter",    "Engineering", 443, "low",    "investigating",  "Multi-model proxy — needs review"),
    ("gemini.google.com",               "google",        "ICU",         443, "high",   "detected",       "PHI risk; Gemini account ties to personal Google"),
    ("api.together.com",                "together",      "Data Science",443, "medium", "approved",       "Approved sandbox for evaluation"),
    ("character.ai",                    "character_ai",  "HR",          443, "medium", "blocked",        "HR-policy violation — entertainment app"),
    ("poe.com",                         "poe",           "Sales",       443, "low",    "blocked",        "Consumer chat aggregator"),
    ("copilot.microsoft.com",           "microsoft_copilot","Finance",  443, "medium", "approved",       "Microsoft 365 Copilot — covered under enterprise BAA"),
    ("api.x.ai",                        "xai",           "Engineering", 443, "low",    "investigating",  "New SDK use; needs BAA review"),
    ("api.replicate.com",               "replicate",     "Imaging",     443, "high",   "blocked",        "Imaging dept attempting unapproved model"),
    ("ambience.ai",                     "ambience_health","Internal Medicine",443,"high","detected",     "Possible scribe vendor — needs governance review"),
    ("abridge.com",                     "abridge",       "Cardiology",  443, "high",   "approved",       "Approved scribe — covered under BAA"),
    ("nabla.com",                       "nabla",         "Pediatrics",  443, "high",   "approved",       "Approved pilot in pediatric clinic"),
    ("cursor.com",                      "cursor",        "Engineering", 443, "low",    "approved",       "Approved developer tool"),
    ("api.openai.com",                  "openai",        "Maternity",   443, "high",   "detected",       "Repeated traffic from L&D nursing station"),
    ("api.anthropic.com",               "anthropic",     "Oncology",    443, "high",   "investigating",  "Suspected note generation"),
    ("chat.deepseek.com",               "deepseek",      "Research",    443, "medium", "approved",       "Approved for non-PHI research workflows"),
    ("you.com",                         "you",           "Communications",443,"low",   "blocked",        "Consumer search aggregator"),
    ("pi.ai",                           "pi",            "Wellness",    443, "low",    "blocked",        "Personal AI — unapproved"),
    ("api.cohere.ai",                   "cohere",        "Sales",       443, "low",    "approved",       "Approved for product copy generation"),
    ("api.together.xyz",                "together",      "Data Science",443, "medium", "detected",       "Detected — under review"),
    ("github.com/copilot",              "github_copilot","Engineering", 443, "low",    "approved",       "Approved org-wide developer tool"),
    ("tabnine.com",                     "tabnine",       "Engineering", 443, "low",    "approved",       "Approved IDE plug-in"),
]


def seed_shadow_ai(db, target: int = 30) -> int:
    if has_at_least(db, ShadowAIDetectionModel, target):
        print(f"    shadow_ai: already >= {target}, skipping")
        return 0
    org_id = first_org_id(db)
    needed = target - db.query(ShadowAIDetectionModel).count()
    selected = SHADOW_AI_DETECTIONS[:needed] if needed > 0 else []
    created = 0
    for host, provider, dept, port, phi, status, notes in selected:
        detected = days_ago(random.randint(0, 21))
        db.add(ShadowAIDetectionModel(
            id=uid("sai_"),
            detected_at=detected,
            source_ip=f"10.{random.randint(0, 50)}.{random.randint(0, 255)}.{random.randint(2, 254)}",
            destination_host=host,
            destination_port=port,
            ai_provider=provider,
            confidence_score=round(random.uniform(0.55, 0.98), 3),
            department=dept,
            phi_risk_level=phi,
            status=status,
            notes=notes,
            organization_id=org_id,
            created_at=detected,
        ))
        created += 1
    db.commit()
    print(f"    shadow_ai: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Scribe audits — mix of hallucinations, omissions, clean notes
# ───────────────────────────────────────────────────────────────────────────

SCRIBE_FIXTURES = [
    # (session_id, model, score, halluc, completeness, attribution, status, findings[])
    ("sc_001", "abridge-v3",   92.4, False, 96.0, 95.2, "complete", []),
    ("sc_002", "nabla-v2",     78.1, True,  88.0, 71.0, "complete",
        [("hallucination", "high", "Note states 'no chest pain' but transcript reports chest tightness")]),
    ("sc_003", "deepscribe-v5",84.5, False, 90.0, 86.0, "complete", []),
    ("sc_004", "abridge-v3",   65.2, True,  60.0, 58.4, "complete",
        [("hallucination", "high", "Vital sign 'BP 200/110' not present in transcript"),
         ("omission",      "medium","Required Plan section missing")]),
    ("sc_005", "suki-v1",      71.8, True,  80.0, 68.5, "pending",
        [("hallucination", "medium","Allergy 'penicillin' mentioned in note but not transcript")]),
    ("sc_006", "abridge-v3",   95.0, False, 100.0,93.0, "complete", []),
    ("sc_007", "nabla-v2",     58.4, True,  65.0, 52.0, "complete",
        [("hallucination", "high", "Reported 'family history of MI' not in transcript"),
         ("attribution",   "medium","Specific lab value 'A1C 7.4' lacks source")]),
    ("sc_008", "deepscribe-v5",89.7, False, 92.0, 91.0, "complete", []),
    ("sc_009", "suki-v1",      62.3, True,  70.0, 56.0, "pending",
        [("hallucination", "medium","Note adds 'patient denies smoking'; not in transcript")]),
    ("sc_010", "abridge-v3",   88.2, False, 96.0, 84.0, "complete", []),
    ("sc_011", "nabla-v2",     74.6, True,  80.0, 70.5, "complete",
        [("hallucination", "high", "Reported 'unchanged from prior visit' is unsupported")]),
    ("sc_012", "deepscribe-v5",91.0, False, 100.0,87.0, "complete", []),
    ("sc_013", "suki-v1",      81.5, False, 88.0, 80.0, "complete", []),
    ("sc_014", "abridge-v3",   76.4, True,  82.0, 73.5, "complete",
        [("attribution",   "low",   "Numeric vital sign not anchored to transcript")]),
    ("sc_015", "nabla-v2",     67.8, True,  72.0, 64.0, "complete",
        [("hallucination", "high", "Diagnosis 'mild gastritis' added without transcript evidence"),
         ("omission",      "medium","Vital signs section incomplete")]),
    ("sc_016", "deepscribe-v5",94.2, False, 100.0,92.5, "complete", []),
    ("sc_017", "abridge-v3",   85.0, False, 92.0, 84.0, "complete", []),
    ("sc_018", "suki-v1",      59.7, True,  68.0, 55.0, "pending",
        [("hallucination", "high", "Medication 'amoxicillin 500mg TID' not mentioned in audio")]),
]


def seed_scribe_audits(db, target: int = 18) -> int:
    if has_at_least(db, ScribeAuditModel, target):
        print(f"    scribe_audits: already >= {target}, skipping")
        return 0
    admin = admin_id(db)
    org_id = first_org_id(db)
    existing_sessions = {a.session_id for a in db.query(ScribeAuditModel).all()}
    created = 0
    for sess, model, score, halluc, comp, attr, status, findings in SCRIBE_FIXTURES:
        if sess in existing_sessions:
            continue
        ts = days_ago(random.randint(0, 30))
        audit = ScribeAuditModel(
            id=uid("sca_"),
            session_id=sess,
            patient_context_hash=hashlib.sha256(f"ctx-{sess}".encode()).hexdigest(),
            ai_model_used=model,
            generated_note_hash=hashlib.sha256(f"note-{sess}".encode()).hexdigest(),
            audit_score=score,
            hallucination_detected=halluc,
            completeness_score=comp,
            attribution_score=attr,
            status=status,
            organization_id=org_id,
            audited_by=admin,
            created_at=ts,
            completed_at=ts + timedelta(minutes=random.randint(2, 45)) if status == "complete" else None,
        )
        db.add(audit)
        db.flush()
        for ftype, sev, desc in findings:
            db.add(ScribeAuditFinding(
                id=uid("scf_"),
                audit_id=audit.id,
                finding_type=ftype,
                severity=sev,
                description=desc,
                suggested_correction="Review the transcript and either anchor the claim or remove it from the note.",
                created_at=ts,
            ))
        created += 1
    db.commit()
    print(f"    scribe_audits: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Prior auth — chained hash, mix of decisions
# ───────────────────────────────────────────────────────────────────────────

PRIOR_AUTH_FIXTURES = [
    # (claim_id, service, ai_recommendation, ai_confidence, final_decision, denial_reason)
    ("CLM-2026-001", "MRI Lumbar Spine",        "Approve — meets medical necessity criteria",        0.91, "approved", None),
    ("CLM-2026-002", "CT Abdomen/Pelvis",       "Deny — conservative therapy not documented",        0.84, "denied",   "Insufficient documentation of conservative care"),
    ("CLM-2026-003", "PET Scan Whole-Body",     "Pending — request additional clinical notes",       0.62, "pending",  None),
    ("CLM-2026-004", "Knee Arthroscopy",        "Approve — failed 6 weeks PT documented",            0.88, "approved", None),
    ("CLM-2026-005", "Bariatric Surgery",       "Approve — meets BMI and comorbidity criteria",      0.93, "approved", None),
    ("CLM-2026-006", "Genetic BRCA Panel",      "Approve — family history meets coverage",           0.95, "approved", None),
    ("CLM-2026-007", "Cosmetic Rhinoplasty",    "Deny — cosmetic, not medically necessary",          0.97, "denied",   "Cosmetic procedure"),
    ("CLM-2026-008", "Spinal Fusion L4-L5",     "Pending — second-level review required",           0.71, "pending",  None),
    ("CLM-2026-009", "Continuous Glucose Monitor","Approve — Type-1 diabetes meets criteria",        0.92, "approved", None),
    ("CLM-2026-010", "Out-of-network ED visit", "Approve — emergent",                                0.99, "approved", None),
    ("CLM-2026-011", "Botox for migraine",      "Deny — fewer than 4 documented migraine days/mo",   0.83, "denied",   "Below frequency threshold"),
    ("CLM-2026-012", "TMS for depression",      "Approve — failed two SSRIs",                        0.86, "approved", None),
    ("CLM-2026-013", "Hip Replacement",         "Approve — failed conservative tx, BMI within range",0.89, "approved", None),
    ("CLM-2026-014", "Inpatient rehab post-CVA","Approve — meets acute rehab criteria",              0.94, "approved", None),
    ("CLM-2026-015", "Experimental gene therapy","Deny — not FDA-approved for indication",           0.96, "denied",   "Not a covered service — experimental"),
    ("CLM-2026-016", "Home health PT",          "Approve — homebound after surgery",                 0.81, "approved", None),
    ("CLM-2026-017", "Sleep study (in-lab)",    "Deny — home sleep study sufficient",                0.79, "denied",   "Lower-cost alternative available"),
    ("CLM-2026-018", "Cardiac rehab",           "Approve — post-MI within 12 months",                0.92, "approved", None),
    ("CLM-2026-019", "Wound vac",               "Pending — additional photo documentation needed",   0.66, "pending",  None),
    ("CLM-2026-020", "Hyperbaric O2 therapy",   "Approve — diabetic ulcer non-healing > 30 days",    0.85, "approved", None),
    ("CLM-2026-021", "Fertility IVF cycle",     "Pending — coverage review (state mandate)",         0.64, "pending",  None),
    ("CLM-2026-022", "Outpatient infusion",     "Approve — Crohn's flare with documented labs",      0.90, "approved", None),
]


def seed_prior_auth(db, target: int = 22) -> int:
    if has_at_least(db, PriorAuthRecord, target):
        print(f"    prior_auth: already >= {target}, skipping")
        return 0
    org_id = first_org_id(db)
    last = (
        db.query(PriorAuthRecord)
        .order_by(PriorAuthRecord.created_at.desc())
        .first()
    )
    prev_hash = last.record_hash if last and getattr(last, "record_hash", None) else "0" * 64
    created = 0
    existing = {r.claim_id for r in db.query(PriorAuthRecord).all()}
    for claim_id, svc, recommendation, conf, decision, denial in PRIOR_AUTH_FIXTURES:
        if claim_id in existing:
            continue
        ts = days_ago(random.randint(0, 60))
        rec_id = uid("pa_")
        patient_hash = hashlib.sha256(f"patient-{claim_id}".encode()).hexdigest()
        payload = f"{rec_id}|{claim_id}|{svc}|{decision}|{prev_hash}"
        record_hash = hashlib.sha256(payload.encode()).hexdigest()
        db.add(PriorAuthRecord(
            id=rec_id,
            patient_id_hash=patient_hash,
            claim_id=claim_id,
            service_type=svc,
            request_date=ts.date().isoformat(),
            decision_date=ts.date().isoformat() if decision != "pending" else None,
            ai_recommendation=recommendation,
            ai_confidence=conf,
            final_decision=decision,
            denial_reason_code=denial[:32] if denial else None,
            ai_rationale=recommendation,
            organization_id=org_id,
            prev_record_hash=prev_hash,
            record_hash=record_hash,
            created_at=ts,
        ))
        prev_hash = record_hash
        created += 1
    db.commit()
    print(f"    prior_auth: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Revenue cycle audits — upcoding/unbundling/modifier flags
# ───────────────────────────────────────────────────────────────────────────

RC_FIXTURES = [
    # (claim_id, risk, upcoding, unbundling, modifier, recommendation)
    ("CLM-RC-001", 12.5, 0, 0, 0, "Clean — no integrity issues detected"),
    ("CLM-RC-002", 78.4, 2, 1, 0, "Review billing codes — possible upcoding on 99214→99215"),
    ("CLM-RC-003", 45.2, 0, 1, 0, "Possible unbundling of CPT 80048+82150"),
    ("CLM-RC-004", 22.1, 0, 0, 1, "Modifier 25 applied without clear documentation"),
    ("CLM-RC-005", 15.0, 0, 0, 0, "Clean"),
    ("CLM-RC-006", 88.7, 3, 2, 1, "High risk — multiple flags, escalate to compliance"),
    ("CLM-RC-007", 8.0,  0, 0, 0, "Clean"),
    ("CLM-RC-008", 35.6, 1, 0, 0, "Possible E/M upcoding"),
    ("CLM-RC-009", 67.1, 1, 1, 1, "Multiple flags — review with provider"),
    ("CLM-RC-010", 19.8, 0, 0, 0, "Clean"),
    ("CLM-RC-011", 51.4, 0, 2, 0, "Unbundling — separate procedures could be a panel"),
    ("CLM-RC-012", 72.9, 2, 1, 1, "High risk — provider education recommended"),
    ("CLM-RC-013", 11.0, 0, 0, 0, "Clean"),
    ("CLM-RC-014", 28.5, 0, 0, 1, "Modifier 59 applied; verify distinct procedure"),
    ("CLM-RC-015", 84.3, 3, 0, 1, "Aggressive upcoding pattern; refer for audit"),
    ("CLM-RC-016", 16.2, 0, 0, 0, "Clean"),
    ("CLM-RC-017", 42.7, 1, 1, 0, "Unbundling and minor upcoding"),
    ("CLM-RC-018", 58.9, 1, 1, 1, "Mixed flags — provider review needed"),
    ("CLM-RC-019", 9.5,  0, 0, 0, "Clean"),
    ("CLM-RC-020", 31.2, 0, 1, 0, "Unbundling on imaging panel"),
    ("CLM-RC-021", 20.4, 0, 0, 0, "Clean"),
    ("CLM-RC-022", 65.0, 2, 0, 1, "Upcoding + modifier issue"),
    ("CLM-RC-023", 14.8, 0, 0, 0, "Clean"),
    ("CLM-RC-024", 39.5, 1, 0, 0, "Single upcoding flag"),
    ("CLM-RC-025", 73.2, 2, 2, 1, "High risk — compliance escalation"),
]


def seed_revenue_cycle(db, target: int = 25) -> int:
    if has_at_least(db, RevenueCycleAudit, target):
        print(f"    revenue_cycle: already >= {target}, skipping")
        return 0
    org_id = first_org_id(db)
    existing = {a.claim_id for a in db.query(RevenueCycleAudit).all()}
    created = 0
    for claim_id, risk, up, ub, mod, rec in RC_FIXTURES:
        if claim_id in existing:
            continue
        ts = days_ago(random.randint(0, 90))
        total_flags = up + ub + mod
        status = "clean" if total_flags == 0 else "flagged" if risk >= 50 else "review"
        cpt_codes = [f"{random.randint(99200, 99499)}" for _ in range(random.randint(1, 3))]
        modifiers = ["25", "59"][:mod]
        findings_payload = []
        for kind, count, severity in (
            ("upcoding", up, "high" if up >= 2 else "medium"),
            ("unbundling", ub, "medium"),
            ("modifier", mod, "low"),
        ):
            for _ in range(count):
                findings_payload.append({
                    "type": kind,
                    "severity": severity,
                    "description": f"Auto-detected {kind} pattern on {claim_id}",
                })
        audit = RevenueCycleAudit(
            id=uid("rc_"),
            claim_id=claim_id,
            claim_date=ts.date().isoformat(),
            provider_id=f"prov_{random.randint(100, 999)}",
            payer_id=random.choice(["medicare", "medicaid", "commercial_a", "commercial_b"]),
            primary_diagnosis_code=random.choice(["E11.65", "I25.10", "J18.9", "M54.5", "Z12.31"]),
            procedure_codes=cpt_codes,
            modifiers=modifiers,
            billed_amount=round(random.uniform(120.0, 4_500.0), 2),
            expected_amount_range={"low": 100.0, "high": 5000.0},
            risk_score=risk,
            findings=findings_payload,
            status=status,
            organization_id=org_id,
            created_at=ts,
            updated_at=ts,
        )
        db.add(audit)
        db.flush()
        # Also persist normalized findings rows
        for f in findings_payload:
            db.add(RevenueCycleFinding(
                id=uid("rcf_"),
                audit_id=audit.id,
                finding_type=f["type"],
                severity=f["severity"],
                description=f["description"],
                affected_codes=cpt_codes[:1],
                estimated_overbilling=round(random.uniform(50.0, 800.0), 2),
                created_at=ts,
            ))
        created += 1
    db.commit()
    print(f"    revenue_cycle: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Adverse events — every severity, varied status
# ───────────────────────────────────────────────────────────────────────────

AE_FIXTURES = [
    # (model_id, event_type, severity, status, description)
    ("mc_sepsis_predictor",     "delayed_alert",       "high",     "investigating", "Sepsis alert fired 47 min after sepsis-3 criteria met"),
    ("mc_chest_xray_triage",    "missed_finding",      "critical", "reported_to_fda","Pneumothorax missed on portable AP study; reader caught"),
    ("mc_readmission_30d",      "false_positive_burst","medium",   "resolved",      "Readmission risk over-triggered after EHR update"),
    ("mc_prior_auth_assistant", "wrong_recommendation","high",     "investigating", "Recommended deny on emergent service; appealed and overturned"),
    ("mc_documentation_assistant","hallucination",     "medium",   "open",          "Note included unsupported allergy entry"),
    ("mc_sepsis_predictor",     "alert_fatigue",       "low",      "resolved",      "Repeated alerts on lab artefacts; threshold tuned"),
    ("mc_chest_xray_triage",    "low_severity_miss",   "medium",   "open",          "Mild consolidation rated 'no finding'"),
    ("mc_readmission_30d",      "score_drift",         "high",     "investigating", "Risk distribution shifted post system upgrade"),
    ("mc_prior_auth_assistant", "decision_bias",       "high",     "investigating", "Disparate denial rate detected on race subgroup"),
    ("mc_documentation_assistant","omission",          "low",      "resolved",      "Missing follow-up plan section"),
    ("mc_sepsis_predictor",     "calibration_loss",    "medium",   "open",          "Calibration shifted during summer flu surge"),
    ("mc_chest_xray_triage",    "delayed_finding",     "low",      "resolved",      "Initial scan flagged late; no patient harm"),
    ("mc_readmission_30d",      "data_pipeline_fail",  "low",      "resolved",      "Discharge feed dropped 0.2% of records"),
    ("mc_prior_auth_assistant", "system_outage",       "low",      "resolved",      "30-min outage during peak; manual fallback used"),
    ("mc_documentation_assistant","privacy_concern",   "high",     "investigating", "PHI not redacted in user-facing draft"),
    ("mc_sepsis_predictor",     "ux_misclick",         "low",      "resolved",      "Provider-reported confusing override flow"),
    ("mc_chest_xray_triage",    "image_artifact",      "medium",   "open",          "Motion artefact misclassified"),
    ("mc_readmission_30d",      "feature_drift",       "medium",   "investigating", "Patient mix changed post merger"),
]


def seed_adverse_events(db, target: int = 18) -> int:
    if has_at_least(db, AdverseEvent, target):
        print(f"    adverse_events: already >= {target}, skipping")
        return 0
    org_id = first_org_id(db)
    sev_map = {
        "low": AdverseEventSeverityDB.LOW,
        "medium": AdverseEventSeverityDB.MEDIUM,
        "high": AdverseEventSeverityDB.HIGH,
        "critical": AdverseEventSeverityDB.CRITICAL,
    }
    status_map = {
        "open": AdverseEventStatusDB.OPEN,
        "investigating": AdverseEventStatusDB.INVESTIGATING,
        "resolved": AdverseEventStatusDB.RESOLVED,
        "reported_to_fda": AdverseEventStatusDB.REPORTED_TO_FDA,
    }
    needed = target - db.query(AdverseEvent).count()
    created = 0
    for model_id, etype, sev, status, desc in AE_FIXTURES[:needed]:
        ts = days_ago(random.randint(1, 80))
        db.add(AdverseEvent(
            id=uid("ae_"),
            organization_id=org_id,
            model_id=model_id,
            agent_id=None,
            event_type=etype,
            severity=sev_map[sev],
            description=desc,
            patient_impact="None reported" if sev in ("low", "medium") else "Possible delay in care; under review",
            reported_by="clinician_oncall",
            status=status_map[status],
            resolved_at=ts + timedelta(days=random.randint(2, 30)) if status == "resolved" else None,
            reported_at=ts,
            created_at=ts,
        ))
        created += 1
    db.commit()
    print(f"    adverse_events: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# PMS reports — quarterly + annual draft + published
# ───────────────────────────────────────────────────────────────────────────

def seed_pms_reports(db, target: int = 12) -> int:
    if has_at_least(db, PMSReport, target):
        print(f"    pms_reports: already >= {target}, skipping")
        return 0
    org_id = first_org_id(db)
    existing = db.query(PMSReport).count()
    needed = target - existing
    created = 0
    quarter_starts = []
    for i in range(needed):
        # Walk back through quarters
        q = (NOW.month - 1) // 3 - i
        year = NOW.year
        while q < 0:
            q += 4
            year -= 1
        start_month = q * 3 + 1
        end_month = (q + 1) * 3 + 1
        end_year = year
        if end_month > 12:
            end_month = 1
            end_year = year + 1
        period_start = datetime(year, start_month, 1)
        period_end = datetime(end_year, end_month, 1)
        if period_end >= NOW:
            continue
        quarter_starts.append((period_start, period_end))

    for period_start, period_end in quarter_starts[:needed]:
        is_annual = period_end.month == 1 and period_end.day == 1 and (period_end.year - period_start.year) >= 1
        rtype = PMSReportTypeDB.PSUR if is_annual else PMSReportTypeDB.QUARTERLY
        rstatus = (
            PMSReportStatusDB.PUBLISHED if random.random() < 0.4
            else PMSReportStatusDB.DRAFT
        )
        report_id = uid("pms_")
        period_label = f"{period_start.date()}..{period_end.date()}"
        report = PMSReport(
            id=report_id,
            organization_id=org_id,
            report_type=rtype,
            status=rstatus,
            period_start=period_start,
            period_end=period_end,
            summary=(
                f"[Auto-generated] {rtype.value.upper()} for {period_label}.\n\n"
                f"Adverse events in period: {random.randint(0, 12)}\n"
                f"Critical events requiring MDR: {random.randint(0, 2)}\n"
                f"AI decisions audited: {random.randint(8_000, 25_000)}\n"
                f"Drift recompute alerts: {random.randint(0, 5)}\n"
                f"Bias-audit failures: {random.randint(0, 2)}"
            ),
            generated_at=period_end + timedelta(days=2),
            created_by="system:pms_auto_generate",
            created_at=period_end + timedelta(days=2),
            updated_at=period_end + timedelta(days=2),
        )
        db.add(report)
        for name, value in [
            ("total_adverse_events", float(random.randint(0, 12))),
            ("critical_events",      float(random.randint(0, 2))),
            ("decisions_audited",    float(random.randint(8_000, 25_000))),
            ("avg_response_ms",      round(random.uniform(120, 380), 1)),
        ]:
            db.add(PMSMetric(
                id=uid("pmsm_"),
                report_id=report_id,
                metric_name=name,
                metric_value=value,
                metric_unit=None,
                computed_at=report.generated_at,
            ))
        created += 1
    db.commit()
    print(f"    pms_reports: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Risk score history — uptrend / downtrend per model
# ───────────────────────────────────────────────────────────────────────────

def seed_risk_history(db, target_per_model: int = 8) -> int:
    cards = db.query(ModelCard).filter(ModelCard.lifecycle_stage == "published").all()
    if not cards:
        print("    risk_history: no published model cards, skipping")
        return 0
    org_id = first_org_id(db)
    created = 0
    for card in cards:
        existing = db.query(RiskScoreHistory).filter(RiskScoreHistory.model_id == card.id).count()
        if existing >= target_per_model:
            continue
        # Build a smooth-ish series
        base = random.uniform(30, 75)
        trend = random.choice([1.5, -1.5, 0.5, -0.5, 0])
        prev = None
        for i in range(target_per_model - existing):
            day_offset = (target_per_model - existing - i) * 7
            value = max(1.0, min(100.0, base + trend * i + random.uniform(-3, 3)))
            level = "critical" if value >= 75 else "high" if value >= 50 else "medium" if value >= 25 else "low"
            db.add(RiskScoreHistory(
                id=uid("rsh_"),
                organization_id=org_id,
                model_id=card.id,
                total_risk=round(value, 1),
                risk_level=level,
                delta=round(value - prev, 1) if prev is not None else None,
                trend="up" if (prev is not None and value > prev + 1) else "down" if (prev is not None and value < prev - 1) else "stable",
                computed_at=days_ago(day_offset),
            ))
            prev = value
            created += 1
    db.commit()
    print(f"    risk_history: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Drift measurements — time series + alerts
# ───────────────────────────────────────────────────────────────────────────

def seed_drift_history(db, target_per_baseline: int = 10) -> int:
    baselines = db.query(DriftBaseline).all()
    if not baselines:
        print("    drift_history: no baselines, skipping")
        return 0
    created = 0
    alerts_added = 0
    for baseline in baselines:
        existing = db.query(DriftMeasurementModel).filter(DriftMeasurementModel.baseline_id == baseline.id).count()
        if existing >= target_per_baseline:
            continue
        for i in range(target_per_baseline - existing):
            day_offset = (target_per_baseline - existing - i) * 3
            psi = round(random.uniform(0.02, 0.35), 4)
            ks_p = round(random.uniform(0.001, 0.4), 4)
            drifted = psi > 0.2 or ks_p < 0.01
            measurement = DriftMeasurementModel(
                id=uid("dm_"),
                baseline_id=baseline.id,
                measurement_time=days_ago(day_offset),
                feature_distributions={"age": [random.gauss(60, 10) for _ in range(20)]},
                psi_scores={"age": psi},
                ks_scores={"age": ks_p},
                performance_current={"auroc": round(random.uniform(0.78, 0.92), 3)},
                drift_detected=drifted,
                drift_magnitude=psi,
            )
            db.add(measurement)
            db.flush()
            if drifted:
                severity = "critical" if psi > 0.3 else "high" if psi > 0.25 else "medium"
                db.add(DriftAlert(
                    id=uid("da_"),
                    measurement_id=measurement.id,
                    alert_type="data_drift",
                    severity=severity,
                    message=f"PSI={psi:.4f}, KS p={ks_p:.4f} on age feature",
                    acknowledged=random.random() < 0.4,
                    created_at=measurement.measurement_time,
                ))
                alerts_added += 1
            created += 1
    db.commit()
    print(f"    drift_measurements: +{created}, drift_alerts: +{alerts_added}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# HITL — top up to a healthy queue with every priority + status
# ───────────────────────────────────────────────────────────────────────────

HITL_FIXTURES = [
    ("Sepsis alert override (urgent)",  "Clinician requesting override on patient with confirmed leukemia",   91.4, "urgent", "pending"),
    ("Drift alert: sepsis-PSI 0.31",    "PSI exceeded threshold on age feature", 78.0, "high", "in_review"),
    ("Bias-audit failure: prior auth",  "Disparity ratio 0.74 on race subgroup",  85.0, "urgent", "pending"),
    ("Approval needed: $4,500 transfer","Vendor invoice exceeds tier-1 limit",   55.0, "high", "pending"),
    ("Approval needed: $850 transfer",  "Routine vendor disbursement",           38.0, "medium","approved"),
    ("Pediatric scribe note review",    "Hallucination flagged on a pediatric encounter", 72.0, "high", "rejected"),
    ("ICU export to non-allowlist host","Block decision needs governance approval", 90.0, "urgent","escalated"),
    ("Data warehouse export review",    "Large dataset export by analyst",        45.0, "medium", "approved"),
    ("Model card publish: chest x-ray", "Awaiting CMIO sign-off",                 68.0, "high", "pending"),
    ("Drift alert: readmission AUC",    "Performance shift detected — needs RCA", 62.0, "high", "in_review"),
    ("Routine PHI access request",      "Analyst needs read on de-identified set",18.0, "low",  "approved"),
    ("Vendor onboarding decision",      "New AI scribe vendor requesting BAA review", 52.0, "medium", "pending"),
    ("Rate limit override request",     "Research team needs higher batch limits", 28.0, "low", "approved"),
    ("Adverse event escalation",        "Sepsis missed-alert event needs CMIO review", 88.0, "urgent", "escalated"),
    ("Policy edit approval",            "Compliance officer updating PHI redaction policy", 33.0, "medium", "approved"),
    ("Model retire decision",           "Documentation assistant moving to retired", 22.0, "low", "approved"),
    ("PSUR draft signoff",              "Q1 PSUR ready for review", 40.0, "medium", "pending"),
    ("Tech file submission review",     "510(k) packet for chest x-ray triage", 65.0, "high", "in_review"),
]


def seed_hitl(db, target: int = 18) -> int:
    if has_at_least(db, HITLReview, target):
        print(f"    hitl_reviews: already >= {target}, skipping")
        return 0
    admin = admin_id(db)
    org_id = first_org_id(db)
    analysts = db.query(User).filter(User.role.in_([UserRole.ANALYST, UserRole.CMIO, UserRole.CLINICAL_USER])).all()
    analyst_ids = [u.id for u in analysts] if analysts else [admin]
    sla_offsets = {"low": 168, "medium": 72, "high": 24, "urgent": 4}
    needed = target - db.query(HITLReview).count()
    created = 0
    for title, desc, risk, prio, status in HITL_FIXTURES[:needed]:
        ts = hours_ago(random.randint(1, 24 * 7))
        review_id = uid("hitl_")
        review = HITLReview(
            id=review_id,
            title=title,
            description=desc,
            ai_decision={"recommendation": "block" if "block" in desc.lower() else "approve", "confidence": round(min(1.0, risk / 100 + 0.1), 2)},
            risk_score=risk,
            status=status,
            priority=prio,
            assigned_to=random.choice(analyst_ids) if status != "pending" else None,
            sla_deadline=ts + timedelta(hours=sla_offsets[prio]),
            organization_id=org_id,
            created_at=ts,
            updated_at=ts + timedelta(minutes=random.randint(0, 240)),
        )
        db.add(review)
        db.flush()
        # Initial audit entry
        payload = f"{review_id}|created|{ts.isoformat()}"
        h = hashlib.sha256(payload.encode()).hexdigest()
        db.add(HITLAuditTrail(
            id=uid("hitt_"),
            review_id=review_id,
            actor_id="system:auto",
            action="auto_create",
            old_status=None,
            new_status="pending",
            comments="Auto-created from policy decision / scheduled job",
            timestamp=ts,
            entry_hash=h,
        ))
        if status not in ("pending",):
            payload2 = f"{review_id}|status_change|{status}|{h}"
            h2 = hashlib.sha256(payload2.encode()).hexdigest()
            db.add(HITLAuditTrail(
                id=uid("hitt_"),
                review_id=review_id,
                actor_id=review.assigned_to or admin,
                action="status_change",
                old_status="pending",
                new_status=status,
                comments=f"Reviewer set status to {status}",
                timestamp=review.updated_at,
                entry_hash=h2,
            ))
        created += 1
    db.commit()
    print(f"    hitl_reviews: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Transparency records — published + draft mix
# ───────────────────────────────────────────────────────────────────────────

TRANSPARENCY_FIXTURES = [
    # (model_name, version, draft, performance_summary, ack_count)
    ("Sepsis Early Warning",     "2.3.1", False, {"auc": 0.872, "sensitivity": 0.81}, 142),
    ("30-Day Readmission Risk",  "1.8.0", False, {"auc": 0.741, "sensitivity": 0.69}, 88),
    ("Chest X-Ray Triage",       "3.0.2", True,  {"auc": 0.94},                       0),
    ("Prior Auth Assistant",     "1.2.0", False, {"agreement": 0.89},                 33),
    ("Documentation Assistant",  "0.9.4", True,  {"completeness": 0.83},              0),
    ("Pneumonia Detector",       "1.4.0", False, {"auc": 0.91, "sensitivity": 0.86},  61),
    ("Stroke Triage Tool",       "2.0.0", True,  {"auc": 0.89},                       0),
    ("Diabetic Retinopathy AI",  "1.1.0", False, {"auc": 0.95, "sensitivity": 0.93}, 204),
    ("Mammography Triage",       "1.0.0", True,  {"auc": 0.88},                       0),
    ("ED Acuity Predictor",      "2.2.0", False, {"auc": 0.84},                       47),
    ("Imaging Order Assistant",  "1.0.5", False, {"agreement": 0.86},                 25),
    ("Discharge Summary Drafter","0.8.0", True,  {"completeness": 0.79},              0),
]


def seed_transparency(db, target: int = 12) -> int:
    if has_at_least(db, TransparencyRecordModel, target):
        print(f"    transparency: already >= {target}, skipping")
        return 0
    admin = admin_id(db)
    org_id = first_org_id(db)
    needed = target - db.query(TransparencyRecordModel).count()
    existing_pairs = {
        (r.model_name, r.model_version)
        for r in db.query(TransparencyRecordModel).all()
    }
    created = 0
    for name, ver, draft, perf, ack_count in TRANSPARENCY_FIXTURES[:needed]:
        if (name, ver) in existing_pairs:
            continue
        ts = days_ago(random.randint(2, 60))
        rec_id = uid("tp_")
        record = TransparencyRecordModel(
            id=rec_id,
            model_name=name,
            model_version=ver,
            algorithm_description=f"Trained on a multi-site clinical cohort with PHI-redacted features. See model card for full details on {name} v{ver}.",
            plain_language_summary=(
                f"{name} is a clinical decision-support tool used by your care team to help "
                f"identify the right next step. It is one of several signals the doctor uses; "
                f"it is not used by itself to make care decisions. A licensed clinician always "
                f"reviews the tool's suggestion before any action is taken."
            ),
            evidence_base="Internal validation cohort + multi-site external validation",
            intended_population="Adult inpatients on general medical wards",
            known_limitations=(
                "Not validated for pediatrics or pregnancy. Performance may vary in populations "
                "underrepresented in the training set; see the model card for subgroup details."
            ),
            performance_summary=perf,
            bias_considerations=(
                "Subgroup analysis was performed during validation. The model meets the 4/5ths "
                "fairness rule across measured groups; see the linked bias audit for details."
            ),
            regulatory_status="510(k) cleared" if not draft else "Pending — pre-submission review",
            published_at=None if draft else ts,
            version_number=1,
            organization_id=org_id,
            created_by=admin,
            created_at=ts,
            updated_at=ts,
        )
        db.add(record)
        db.flush()
        db.add(TransparencyVersion(
            id=uid("tpv_"),
            record_id=rec_id,
            version_number=1,
            content_snapshot={
                "model_name": name,
                "model_version": ver,
                "plain_language_summary": record.plain_language_summary,
                "intended_population": record.intended_population,
                "known_limitations": record.known_limitations,
                "performance_summary": perf,
                "bias_considerations": record.bias_considerations,
                "auto_generated_from_model_card": None,
            },
            change_summary="Initial publication" if not draft else "Auto-drafted from model card publish",
            published_by=admin,
            published_at=ts,
        ))
        for _ in range(ack_count):
            db.add(TransparencyAcknowledgment(
                id=uid("tpa_"),
                record_id=rec_id,
                acknowledged_by=f"patient_{uuid.uuid4().hex[:8]}",
                acknowledged_at=ts + timedelta(days=random.randint(1, 90)),
                role_at_time="patient",
                ip_address_hash=hashlib.sha256(f"ip-{random.randint(0, 10**10)}".encode()).hexdigest()[:32],
            ))
        created += 1
    db.commit()
    print(f"    transparency: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Technical files — 510(k) and EU MDR mix
# ───────────────────────────────────────────────────────────────────────────

TECH_FILE_FIXTURES = [
    # (title, regulatory_type, product, version, lifecycle, sections[(type, content)])
    ("Sepsis EW — 510(k) Submission",     RegulatoryTypeDB.FDA_510K, "Sepsis EW",          "2.3.1", TechnicalFileLifecycleDB.SUBMITTED,
     [("device_description","Auto-populated from model card mc_sepsis_predictor."),
      ("intended_use","Sepsis early warning for adult inpatients."),
      ("performance_data","Internal+external validation; AUC 0.872, sensitivity 0.81."),
      ("risk_management","Continuous monitoring via Sentinel; 5 open adverse events."),
      ("clinical_evaluation","8 audits across sex/race/age subgroups, all pass 4/5ths."),
      ("predicate_comparison","K181234 — comparable indications, similar performance.")]),
    ("Chest X-Ray Triage — 510(k)",       RegulatoryTypeDB.FDA_510K, "Chest X-Ray Triage", "3.0.2", TechnicalFileLifecycleDB.UNDER_REVIEW,
     [("device_description","Auto-populated from model card mc_chest_xray_triage."),
      ("intended_use","Prioritize chest x-rays with critical findings."),
      ("performance_data","Multi-site validation; AUC 0.94 (pneumothorax)."),
      ("risk_management","FDA SaMD class II controls; 1 critical adverse event reported."),
      ("clinical_evaluation","Pre-submission audit running."),
      ("predicate_comparison","K201234 — comparable triage classifier.")]),
    ("Pneumonia Detector — EU MDR",       RegulatoryTypeDB.EU_MDR, "Pneumonia Detector", "1.4.0", TechnicalFileLifecycleDB.APPROVED,
     [("device_description","Notified Body 2797 reviewed."),
      ("intended_use","Triage chest x-rays for pneumonia in adult ED patients."),
      ("performance_data","Class IIb device; AUC 0.91."),
      ("risk_management","Continuous PMS via Sentinel quarterly + annual reports."),
      ("clinical_evaluation","8-site clinical evidence package."),
      ("predicate_comparison","Equivalence to legacy CAD predicate."),
      ("clinical_post_market_plan","Quarterly review of adverse events + drift alerts."),
      ("clinical_evidence","Multi-centre trial n=4,200 patients.")]),
    ("Diabetic Retinopathy AI — EU MDR",  RegulatoryTypeDB.EU_MDR, "Diabetic Retinopathy AI", "1.1.0", TechnicalFileLifecycleDB.APPROVED,
     [("device_description","Class IIa autonomous diagnostic device."),
      ("intended_use","Detect referable diabetic retinopathy in adult diabetics."),
      ("performance_data","Sensitivity 0.93, specificity 0.89."),
      ("risk_management","Annual PSUR + monthly drift recompute."),
      ("clinical_evaluation","Multi-site European cohort."),
      ("predicate_comparison","Equivalent to first-gen DR screener (CE Mark 2019)."),
      ("clinical_post_market_plan","Monthly drift dashboard review."),
      ("clinical_evidence","CE Mark dossier 2024.")]),
    ("Stroke Triage — 510(k) Pre-Sub",    RegulatoryTypeDB.FDA_510K, "Stroke Triage Tool", "2.0.0", TechnicalFileLifecycleDB.DRAFT,
     [("device_description","Auto-populated draft."),
      ("intended_use","Identify likely large-vessel occlusions in CT scans."),
      ("performance_data","Validation in progress."),
      ("risk_management","To be authored before submission.")]),
    ("Mammography Triage — 510(k)",       RegulatoryTypeDB.FDA_510K, "Mammography Triage", "1.0.0", TechnicalFileLifecycleDB.DRAFT,
     [("device_description","Pre-submission draft."),
      ("intended_use","Triage screening mammograms for radiologist review."),
      ("performance_data","Multi-site reader study planned."),
      ("risk_management","Risk file in progress.")]),
    ("ED Acuity — EU MDR",                RegulatoryTypeDB.EU_MDR, "ED Acuity Predictor", "2.2.0", TechnicalFileLifecycleDB.UNDER_REVIEW,
     [("device_description","Class IIa decision-support."),
      ("intended_use","Predict ED-admission acuity."),
      ("performance_data","AUC 0.84 across 6 sites."),
      ("risk_management","Quarterly PSUR submission."),
      ("clinical_evaluation","6-site prospective validation."),
      ("predicate_comparison","Equivalent to ESI."),
      ("clinical_post_market_plan","Quarterly drift + adverse-event review."),
      ("clinical_evidence","Prospective n=12,000.")]),
    ("Discharge Summary — Both",          RegulatoryTypeDB.BOTH,  "Discharge Drafter",  "0.8.0", TechnicalFileLifecycleDB.DRAFT,
     [("device_description","Documentation assistant — non-medical-device classification."),
      ("intended_use","Generate discharge summary drafts from EHR data."),
      ("performance_data","Completeness 0.79 vs human-authored gold."),
      ("risk_management","Privacy + hallucination controls in place.")]),
]


def seed_technical_files(db, target: int = 8) -> int:
    if has_at_least(db, TechnicalFile, target):
        print(f"    technical_files: already >= {target}, skipping")
        return 0
    admin = admin_id(db)
    org_id = first_org_id(db)
    existing_titles = {t.title for t in db.query(TechnicalFile).all()}
    needed = target - db.query(TechnicalFile).count()
    created = 0
    for title, rtype, product, version, lifecycle, sections in TECH_FILE_FIXTURES[:needed]:
        if title in existing_titles:
            continue
        ts = days_ago(random.randint(2, 90))
        file_id = uid("tf_")
        tf = TechnicalFile(
            id=file_id,
            organization_id=org_id,
            title=title,
            regulatory_type=rtype,
            product_name=product,
            device_version=version,
            lifecycle_stage=lifecycle,
            created_by=admin,
            created_at=ts,
            updated_at=ts,
        )
        db.add(tf)
        for index, (stype, content) in enumerate(sections):
            db.add(TechnicalFileSection(
                id=uid("tfs_"),
                file_id=file_id,
                section_type=stype,
                content=content,
                order_index=index,
                auto_generated=True,
                created_at=ts,
                updated_at=ts,
            ))
        created += 1
    db.commit()
    print(f"    technical_files: +{created}")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────────────────

def main():
    print("=== Sentinel — Extended demo seeder (Tier 2 + Tier 3) ===")
    db = SessionLocal()
    try:
        seed_audit_logs(db)
        seed_alerts(db)
        seed_shadow_ai(db)
        seed_scribe_audits(db)
        seed_prior_auth(db)
        seed_revenue_cycle(db)
        seed_adverse_events(db)
        seed_pms_reports(db)
        seed_risk_history(db)
        seed_drift_history(db)
        seed_hitl(db)
        seed_transparency(db)
        seed_technical_files(db)
        print("=== Done ===")
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
