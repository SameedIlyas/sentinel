"""
Seed script for the healthcare governance tables that `seed_demo_data.py` does
not cover. Idempotent — checks for existing rows before inserting.

Tables seeded (15 total across 12 model files):
    model_cards, model_card_versions, model_card_metrics, model_card_reviews
    bias_audits, bias_audit_subgroups, bias_audit_results
    drift_baselines, drift_measurements, drift_alerts
    hitl_reviews, hitl_assignments, hitl_audit_trail
    shadow_ai_detections, shadow_ai_allowlist
    scribe_audits, scribe_audit_findings
    transparency_records, transparency_versions, transparency_acknowledgments
    prior_auth_records (with chained hash)
    revenue_cycle_audits, revenue_cycle_findings, coding_benchmarks
    technical_files, technical_file_sections, technical_file_versions
    adverse_events, pms_reports, pms_metrics
    risk_scores, risk_score_history, risk_configurations, risk_regulatory_mapping

Usage:
    alembic upgrade head
    python create_admin_user.py --default
    python seed_demo_data.py
    python seed_demo_healthcare.py        # <-- this script
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from policy_engine.database import SessionLocal, engine, Base  # noqa: E402

# Import every healthcare model so SQLAlchemy registers each table.
from policy_engine.models.model_card import (  # noqa: E402
    ModelCard, ModelCardVersion, ModelCardMetric, ModelCardReview,
)
from policy_engine.models.bias_audit import (  # noqa: E402
    BiasAuditModel, BiasAuditSubgroup, BiasAuditResultModel,
)
from policy_engine.models.drift import (  # noqa: E402
    DriftBaseline, DriftMeasurementModel, DriftAlert,
)
from policy_engine.models.hitl import (  # noqa: E402
    HITLReview, HITLAssignment, HITLAuditTrail,
)
from policy_engine.models.shadow_ai import (  # noqa: E402
    ShadowAIDetectionModel, ShadowAIAllowlist,
)
from policy_engine.models.scribe_audit import (  # noqa: E402
    ScribeAuditModel, ScribeAuditFinding,
)
from policy_engine.models.transparency import (  # noqa: E402
    TransparencyRecordModel, TransparencyVersion, TransparencyAcknowledgment,
)
from policy_engine.models.prior_auth import PriorAuthRecord  # noqa: E402
from policy_engine.models.revenue_cycle import (  # noqa: E402
    RevenueCycleAudit, RevenueCycleFinding, CodingBenchmark,
)
from policy_engine.models.technical_file import (  # noqa: E402
    TechnicalFile, TechnicalFileSection, TechnicalFileVersion,
)
from policy_engine.models.post_market import AdverseEvent, PMSReport, PMSMetric  # noqa: E402
from policy_engine.models.risk_score import (  # noqa: E402
    RiskScore, RiskScoreHistory, RiskConfiguration, RiskRegulatoryMapping,
)
from policy_engine.models.user import User, UserRole  # noqa: E402


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────

now = datetime.utcnow()


def uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def days_ago(d: int) -> datetime:
    return now - timedelta(days=d, hours=random.randint(0, 23))


def hours_ago(h: int) -> datetime:
    return now - timedelta(hours=h, minutes=random.randint(0, 59))


def get_admin_id(db) -> str:
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    return admin.id if admin else "user_system"


def already_populated(db, model_cls, threshold: int = 1) -> bool:
    return db.query(model_cls).count() >= threshold


# ───────────────────────────────────────────────────────────────────────────
# Static demo data
# ───────────────────────────────────────────────────────────────────────────

DEMO_MODEL_CARDS = [
    {
        "id": "mc_sepsis_predictor",
        "name": "Sepsis Early Warning Model",
        "version": "2.3.1",
        "stage": "published",
        "intended_use": "Early identification of sepsis risk in ED and inpatient settings",
        "indications": "Adult patients (≥18) admitted to ED, ICU, or general medicine wards",
        "contraindications": "Pediatric patients; obstetric patients",
        "training_source": "MIMIC-IV + 4 partner health systems (n=1.2M encounters, 2018-2024)",
        "fda_status": "510(k) Cleared (K231847)",
        "perf": {"AUC": 0.872, "sensitivity": 0.81, "specificity": 0.83, "PPV": 0.42},
        "bias": {"max_disparity_ratio": 1.18, "subgroups_evaluated": 8, "passes_4_5ths_rule": True},
    },
    {
        "id": "mc_readmission_30d",
        "name": "30-Day Readmission Risk",
        "version": "1.8.0",
        "stage": "published",
        "intended_use": "Identify discharged patients at high risk of readmission within 30 days",
        "indications": "Adult inpatients at hospital discharge",
        "contraindications": "Hospice / comfort-care discharges",
        "training_source": "Internal claims + clinical EHR (n=480K, 2019-2024)",
        "fda_status": "Not a medical device (administrative tool)",
        "perf": {"AUC": 0.741, "sensitivity": 0.69, "specificity": 0.72},
        "bias": {"max_disparity_ratio": 1.34, "subgroups_evaluated": 6, "passes_4_5ths_rule": False},
    },
    {
        "id": "mc_chest_xray_triage",
        "name": "Chest X-Ray Triage Classifier",
        "version": "3.0.2",
        "stage": "review",
        "intended_use": "Prioritize chest X-rays with critical findings (pneumothorax, consolidation)",
        "indications": "Adult chest X-rays in ED radiology workflow",
        "contraindications": "Pediatric imaging; portable bedside studies under suboptimal conditions",
        "training_source": "CheXpert + Stanford ML Group + 3 partner sites (n=750K studies)",
        "fda_status": "510(k) Submitted — under review",
        "perf": {"AUC_pneumothorax": 0.94, "AUC_consolidation": 0.88, "sensitivity": 0.91},
        "bias": {"max_disparity_ratio": 1.08, "subgroups_evaluated": 5, "passes_4_5ths_rule": True},
    },
    {
        "id": "mc_prior_auth_assistant",
        "name": "Prior Authorization Decision Support",
        "version": "1.2.0",
        "stage": "published",
        "intended_use": "Recommend prior-authorization decisions for high-volume procedures",
        "indications": "Routine outpatient procedures (CPT 99000-99999)",
        "contraindications": "Emergent/urgent procedures; experimental therapies",
        "training_source": "Internal payer-side adjudication history (n=2.1M claims)",
        "fda_status": "Not a medical device (administrative)",
        "perf": {"agreement_with_human": 0.89, "appeal_rate": 0.07},
        "bias": {"max_disparity_ratio": 1.22, "subgroups_evaluated": 4, "passes_4_5ths_rule": False},
    },
    {
        "id": "mc_documentation_assistant",
        "name": "Clinical Documentation Assistant",
        "version": "0.9.4",
        "stage": "draft",
        "intended_use": "Generate H&P note drafts from ambient encounter audio",
        "indications": "Outpatient primary care visits",
        "contraindications": "Mental health visits; pediatrics under 12; non-English encounters",
        "training_source": "Synthetic encounter dataset + opt-in clinician corpus (n=85K notes)",
        "fda_status": "Pending — not yet submitted",
        "perf": {"BLEU": 0.62, "completeness": 0.83, "hallucination_rate": 0.04},
        "bias": {"max_disparity_ratio": None, "subgroups_evaluated": 0, "passes_4_5ths_rule": None},
    },
]

DEMO_BIAS_AUDITS = [
    # (audit_name, model_card_id, status, subgroups -> [(name, type, n, ref_metric, group_metric, threshold)])
    {
        "id": "ba_sepsis_2025_q1",
        "model_card_id": "mc_sepsis_predictor",
        "name": "Sepsis Model — Q1 2026 Fairness Audit",
        "status": "complete",
        "dataset": "Internal validation cohort (n=42,318 admissions, 2025-Q4)",
        "subgroups": [
            ("Female",  "sex",       21240, 0.872, 0.866, 0.80),
            ("Male",    "sex",       21078, 0.872, 0.878, 0.80),
            ("Black",   "race",       8512, 0.872, 0.834, 0.80),
            ("Hispanic","race",       6201, 0.872, 0.851, 0.80),
            ("White",   "race",      24304, 0.872, 0.881, 0.80),
            ("Asian",   "race",       3301, 0.872, 0.862, 0.80),
            ("Age 18-44","age",      11420, 0.872, 0.880, 0.80),
            ("Age 65+", "age",       17188, 0.872, 0.851, 0.80),
        ],
    },
    {
        "id": "ba_readmission_2025_q4",
        "model_card_id": "mc_readmission_30d",
        "name": "Readmission Model — Q4 2025 Fairness Audit",
        "status": "complete",
        "dataset": "Discharge cohort (n=18,422 admissions, 2025-Q3)",
        "subgroups": [
            ("Female", "sex",  9211, 0.741, 0.732, 0.80),
            ("Male",   "sex",  9211, 0.741, 0.748, 0.80),
            ("Black",  "race", 3801, 0.741, 0.681, 0.80),  # FAILS — disparity > 0.85
            ("Hispanic","race",2914, 0.741, 0.703, 0.80),
            ("White",  "race",10822, 0.741, 0.755, 0.80),
            ("Medicare-only","insurance", 6021, 0.741, 0.711, 0.80),
        ],
    },
    {
        "id": "ba_xray_2026_q1",
        "model_card_id": "mc_chest_xray_triage",
        "name": "Chest X-Ray Triage — Pre-submission Fairness Audit",
        "status": "running",
        "dataset": "Multi-site validation (n=8,400 studies, 2025-Q4)",
        "subgroups": [],  # not yet completed
    },
    {
        "id": "ba_prior_auth_2025_q4",
        "model_card_id": "mc_prior_auth_assistant",
        "name": "Prior Auth — Disparity Audit",
        "status": "complete",
        "dataset": "Adjudication sample (n=12,000 decisions)",
        "subgroups": [
            ("Female",  "sex",  6021, 0.89, 0.88, 0.80),
            ("Male",    "sex",  5979, 0.89, 0.90, 0.80),
            ("Black",   "race", 2402, 0.89, 0.74, 0.80),  # FAILS
            ("White",   "race", 7301, 0.89, 0.91, 0.80),
        ],
    },
]

DEMO_RISK_FACTORS = [
    # model_id, severity_score, exposure_score, reg_penalty, regulatory_flags
    ("mc_sepsis_predictor",         71.2, 68.5, 1.15, ["FDA_SAMD", "HIPAA"]),
    ("mc_readmission_30d",          54.8, 71.0, 1.05, ["HIPAA", "CMS_FALSE_CLAIMS"]),
    ("mc_chest_xray_triage",        77.4, 64.2, 1.20, ["FDA_SAMD", "HIPAA", "ONC_HTI1"]),
    ("mc_prior_auth_assistant",     42.6, 75.8, 1.10, ["HIPAA", "CMS_FALSE_CLAIMS"]),
    ("mc_documentation_assistant",  38.2, 51.5, 1.00, ["HIPAA"]),
    ("agent_research_assist",       21.0, 28.4, 1.00, []),
    ("agent_financial_analyst",     56.1, 62.3, 1.05, ["CMS_FALSE_CLAIMS"]),
    ("agent_customer_support",      18.7, 33.0, 1.00, ["HIPAA"]),
]


def _risk_level(total: float) -> str:
    if total >= 75:
        return "critical"
    if total >= 50:
        return "high"
    if total >= 25:
        return "medium"
    return "low"


# ───────────────────────────────────────────────────────────────────────────
# Seed functions
# ───────────────────────────────────────────────────────────────────────────


def seed_model_cards(db) -> int:
    if already_populated(db, ModelCard):
        print("    Model cards: already populated, skipping")
        return 0
    admin = get_admin_id(db)
    created = 0
    for mc in DEMO_MODEL_CARDS:
        card = ModelCard(
            id=mc["id"],
            name=mc["name"],
            version=mc["version"],
            lifecycle_stage=mc["stage"],
            intended_use=mc["intended_use"],
            clinical_indications=mc["indications"],
            contraindications=mc["contraindications"],
            training_data_source=mc["training_source"],
            performance_metrics=mc["perf"],
            bias_summary=mc["bias"],
            fda_status=mc["fda_status"],
            chai_version="2.0",
            created_by=admin,
            created_at=days_ago(random.randint(30, 180)),
            updated_at=days_ago(random.randint(0, 14)),
        )
        db.add(card)
        # One published version snapshot per card that is published or in review
        if mc["stage"] in ("published", "review"):
            db.add(ModelCardVersion(
                id=uid("mcv_"),
                model_card_id=mc["id"],
                version_number=mc["version"],
                content={
                    "intended_use": mc["intended_use"],
                    "indications": mc["indications"],
                    "performance": mc["perf"],
                    "bias_summary": mc["bias"],
                },
                published_by=admin,
                published_at=days_ago(random.randint(7, 60)),
                changelog=f"Initial published version {mc['version']}",
            ))
        # Performance metrics, one per perf key
        for metric_name, metric_value in mc["perf"].items():
            if not isinstance(metric_value, (int, float)):
                continue
            db.add(ModelCardMetric(
                id=uid("mcm_"),
                model_card_id=mc["id"],
                metric_name=metric_name,
                metric_value=float(metric_value),
                metric_type="performance",
                evaluation_date=days_ago(random.randint(7, 60)),
            ))
        # One review on published cards
        if mc["stage"] == "published":
            db.add(ModelCardReview(
                id=uid("mcr_"),
                model_card_id=mc["id"],
                reviewer_id=admin,
                reviewer_role="cmio",
                decision="approve",
                comments="Approved for production use after fairness review.",
                reviewed_at=days_ago(random.randint(7, 30)),
            ))
        created += 1
    db.commit()
    print(f"    Model cards: {created} created")
    return created


def seed_bias_audits(db) -> int:
    if already_populated(db, BiasAuditModel):
        print("    Bias audits: already populated, skipping")
        return 0
    admin = get_admin_id(db)
    created = 0
    for ba in DEMO_BIAS_AUDITS:
        completed = ba["status"] == "complete"
        audit = BiasAuditModel(
            id=ba["id"],
            model_card_id=ba["model_card_id"],
            audit_name=ba["name"],
            status=ba["status"],
            dataset_description=ba["dataset"],
            created_by=admin,
            created_at=days_ago(random.randint(7, 90)),
            completed_at=days_ago(random.randint(1, 7)) if completed else None,
        )
        db.add(audit)
        for sg_name, sg_type, n, ref, val, thr in ba["subgroups"]:
            sg = BiasAuditSubgroup(
                id=uid("bsg_"),
                audit_id=ba["id"],
                subgroup_name=sg_name,
                subgroup_type=sg_type,
                sample_size=n,
            )
            db.add(sg)
            db.flush()  # ensure subgroup id exists for FK
            disparity = round(val / ref, 3) if ref else 1.0
            db.add(BiasAuditResultModel(
                id=uid("bres_"),
                audit_id=ba["id"],
                subgroup_id=sg.id,
                metric_name="AUC",
                metric_value=val,
                reference_value=ref,
                disparity_ratio=disparity,
                passes_threshold=disparity >= thr,
                threshold_used=thr,
            ))
        created += 1
    db.commit()
    print(f"    Bias audits: {created} created (with subgroups + results)")
    return created


def seed_drift(db) -> int:
    if already_populated(db, DriftBaseline):
        print("    Drift: already populated, skipping")
        return 0
    created_baselines = 0
    created_meas = 0
    created_alerts = 0
    for mc in DEMO_MODEL_CARDS[:3]:  # 3 baselines
        baseline_id = uid("dbl_")
        db.add(DriftBaseline(
            id=baseline_id,
            model_id=mc["id"],
            baseline_name=f"{mc['name']} v{mc['version']} baseline (training)",
            feature_distributions={
                "age_mean": 58.4, "age_std": 18.2,
                "ed_visits_last_year_mean": 1.8,
                "comorbidity_count_mean": 2.4,
            },
            performance_baseline=mc["perf"],
            created_at=days_ago(random.randint(30, 120)),
        ))
        created_baselines += 1
        # 4 weekly measurements per baseline; last one drifting
        for week in range(4):
            measurement_time = days_ago((3 - week) * 7)
            drifted = (week == 3 and mc["id"] == "mc_readmission_30d")
            magnitude = 0.42 if drifted else round(random.uniform(0.03, 0.18), 3)
            measurement = DriftMeasurementModel(
                id=uid("dm_"),
                baseline_id=baseline_id,
                measurement_time=measurement_time,
                feature_distributions={
                    "age_mean": 58.4 + (week * 0.4),
                    "comorbidity_count_mean": 2.4 + (week * 0.05),
                },
                psi_scores={
                    "age": round(random.uniform(0.01, 0.08) + (0.25 if drifted else 0), 3),
                    "comorbidity_count": round(random.uniform(0.01, 0.06), 3),
                },
                ks_scores={
                    "age_p_value": 0.001 if drifted else round(random.uniform(0.15, 0.95), 3),
                },
                performance_current={
                    "AUC": mc["perf"].get("AUC", 0.85) - (0.06 if drifted else round(random.uniform(0.001, 0.01), 4)),
                },
                drift_detected=drifted,
                drift_magnitude=magnitude,
            )
            db.add(measurement)
            db.flush()
            created_meas += 1
            if drifted:
                db.add(DriftAlert(
                    id=uid("da_"),
                    measurement_id=measurement.id,
                    alert_type="performance_degradation",
                    severity="high",
                    message=f"AUC dropped {(0.06 / mc['perf'].get('AUC', 0.85)) * 100:.1f}% vs. baseline; PSI on 'age' indicates feature distribution shift",
                    acknowledged=False,
                    created_at=measurement_time + timedelta(minutes=15),
                ))
                created_alerts += 1
    db.commit()
    print(f"    Drift: {created_baselines} baselines, {created_meas} measurements, {created_alerts} alerts")
    return created_baselines


def seed_hitl(db) -> int:
    if already_populated(db, HITLReview):
        print("    HITL: already populated, skipping")
        return 0
    admin = get_admin_id(db)
    analysts = db.query(User).filter(User.role == UserRole.ANALYST).all()
    analyst_ids = [u.id for u in analysts] if analysts else [admin]
    reviews = [
        ("Sepsis alert override request",       "Clinician requested override of sepsis alert for 78yo patient — rationale: acute leukocytosis from chemotherapy", 78.4, "high",   "pending"),
        ("Readmission flag dispute",            "Discharge planner contesting high-risk flag — patient has confirmed home-health support",                          51.2, "medium", "in_review"),
        ("X-ray critical-finding triage",       "AI flagged pneumothorax on portable ED study; radiologist requesting validation",                                   84.7, "urgent", "pending"),
        ("Prior auth denial recommendation",    "AI recommended deny for pre-authorization of MRI lumbar spine; patient has 6w of conservative therapy documented", 36.8, "medium", "approved"),
        ("Documentation hallucination flag",    "Scribe AI generated 'no chest pain' but patient reported chest tightness in audio",                               72.0, "high",   "rejected"),
        ("Adverse-event escalation review",     "Bias audit triggered escalation for readmission model — disparity ratio 0.92 across race subgroups",              66.5, "high",   "escalated"),
    ]
    sla_offsets = {"low": 168, "medium": 72, "high": 24, "urgent": 4}
    created = 0
    for title, desc, risk, prio, status in reviews:
        review_id = uid("hitl_")
        created_at = hours_ago(random.randint(1, 96))
        review = HITLReview(
            id=review_id,
            title=title,
            description=desc,
            ai_decision={"recommendation": "block" if "deny" in desc.lower() else "approve", "confidence": round(risk / 100 + 0.05, 2)},
            risk_score=risk,
            status=status,
            priority=prio,
            assigned_to=random.choice(analyst_ids),
            sla_deadline=created_at + timedelta(hours=sla_offsets[prio]),
            created_at=created_at,
            updated_at=created_at + timedelta(minutes=random.randint(5, 240)),
        )
        db.add(review)
        # Assignment audit
        db.add(HITLAssignment(
            id=uid("hita_"),
            review_id=review_id,
            assigned_to=review.assigned_to,
            assigned_by=admin,
            assigned_at=created_at,
            completed_at=review.updated_at if status in ("approved", "rejected") else None,
        ))
        # Status-change trail entry
        prev_hash = ""
        entry_payload = f"{review_id}|created|{created_at.isoformat()}"
        entry_hash = hashlib.sha256(entry_payload.encode()).hexdigest()
        db.add(HITLAuditTrail(
            id=uid("hitt_"),
            review_id=review_id,
            actor_id=admin,
            action="created",
            old_status=None,
            new_status="pending",
            comments="Initial submission",
            timestamp=created_at,
            entry_hash=entry_hash,
        ))
        prev_hash = entry_hash
        if status != "pending":
            new_payload = f"{review_id}|status_change|{status}|{prev_hash}"
            new_hash = hashlib.sha256(new_payload.encode()).hexdigest()
            db.add(HITLAuditTrail(
                id=uid("hitt_"),
                review_id=review_id,
                actor_id=review.assigned_to,
                action="status_change",
                old_status="pending",
                new_status=status,
                comments=f"Reviewer set status to {status}",
                timestamp=review.updated_at,
                entry_hash=new_hash,
            ))
        created += 1
    db.commit()
    print(f"    HITL: {created} reviews (with assignments + audit trail)")
    return created


def seed_shadow_ai(db) -> int:
    if already_populated(db, ShadowAIDetectionModel):
        print("    Shadow AI: already populated, skipping")
        return 0
    admin = get_admin_id(db)
    detections = [
        ("api.openai.com",       443, "OpenAI",     0.98, "high",     "10.42.18.7",  "Cardiology",       "detected",     None),
        ("api.anthropic.com",    443, "Anthropic",  0.96, "medium",   "10.42.21.4",  "Radiology",        "detected",     None),
        ("api.openai.com",       443, "OpenAI",     0.99, "high",     "10.42.34.2",  "Pharmacy",         "reviewed",     "Approved for non-PHI workflows"),
        ("generativelanguage.googleapis.com", 443, "Google Gemini", 0.92, "low",     "10.42.5.18",  "Marketing",        "allowlisted",  "Marketing-only; no PHI risk"),
        ("api.cohere.ai",        443, "Cohere",     0.88, "medium",   "10.42.18.9",  "IT",               "detected",     None),
        ("character.ai",         443, "Character.AI", 0.94, "critical","10.42.50.1", "Unknown",          "detected",     "Personal use suspected; PHI exposure possible"),
        ("ollama.example-cdn.com", 11434, "Self-hosted Ollama", 0.71, "low", "10.42.99.7", "Engineering", "allowlisted", "Local-only; no external PHI flow"),
        ("api.mistral.ai",       443, "Mistral",    0.85, "medium",   "10.42.21.7",  "Operations",       "detected",     None),
    ]
    for host, port, provider, conf, phi_risk, src_ip, dept, status, notes in detections:
        db.add(ShadowAIDetectionModel(
            id=uid("sai_"),
            detected_at=hours_ago(random.randint(1, 168)),
            source_ip=src_ip,
            destination_host=host,
            destination_port=port,
            ai_provider=provider,
            confidence_score=conf,
            department=dept,
            phi_risk_level=phi_risk,
            status=status,
            notes=notes,
            created_at=hours_ago(random.randint(1, 168)),
        ))
    # Allowlist entries
    db.add(ShadowAIAllowlist(
        id=uid("sal_"),
        host_pattern="generativelanguage.googleapis.com",
        reason="Marketing-only generative copy; no PHI flow",
        approved_by=admin,
        approved_at=days_ago(7),
        created_at=days_ago(7),
    ))
    db.add(ShadowAIAllowlist(
        id=uid("sal_"),
        host_pattern="*.example-cdn.com",
        reason="Self-hosted Ollama on internal network",
        approved_by=admin,
        approved_at=days_ago(14),
        created_at=days_ago(14),
    ))
    db.commit()
    print(f"    Shadow AI: {len(detections)} detections + 2 allowlist entries")
    return len(detections)


def seed_scribe_audits(db) -> int:
    if already_populated(db, ScribeAuditModel):
        print("    Scribe audits: already populated, skipping")
        return 0
    admin = get_admin_id(db)
    audits = [
        # session_id, model, audit_score, hallucination, completeness, attribution, status, findings
        ("sess_2026_05_07_1432", "Nuance DAX", 87.4, False, 92.1, 100.0, "complete",
         []),
        ("sess_2026_05_08_0911", "Abridge",    71.8, True,  85.6, 88.0,  "complete",
         [("hallucination", "high",   "Note states 'no chest pain' but transcript has 'some chest tightness on exertion'", "Replace with: 'Reports intermittent chest tightness on exertion'"),
          ("attribution",   "medium", "Plan section did not cite the patient's stated medication intolerance", "Add reference to alprazolam adverse-reaction history")]),
        ("sess_2026_05_08_1245", "Nabla",      94.2, False, 96.8, 100.0, "complete",
         []),
        ("sess_2026_05_09_0820", "Nuance DAX", 62.5, True,  78.0, 75.0,  "in_review",
         [("hallucination", "critical", "AI generated 'denies suicidal ideation' — not present in audio transcript", "Remove sentence; reviewer to confirm directly"),
          ("completeness",  "high",     "Missing review of systems for cardiovascular per template", "Add ROS - cardiovascular section")]),
        ("sess_2026_05_09_1015", "Abridge",    81.0, False, 88.4, 95.0,  "pending",
         []),
    ]
    for sess, model, score, hall, comp, attr, status, findings in audits:
        audit_id = uid("sa_")
        completed_at = hours_ago(random.randint(1, 24)) if status == "complete" else None
        db.add(ScribeAuditModel(
            id=audit_id,
            session_id=sess,
            patient_context_hash=hashlib.sha256(f"patient_{sess}".encode()).hexdigest()[:32],
            ai_model_used=model,
            generated_note_hash=hashlib.sha256(f"note_{sess}".encode()).hexdigest()[:32],
            audit_score=score,
            hallucination_detected=hall,
            completeness_score=comp,
            attribution_score=attr,
            status=status,
            audited_by=admin,
            created_at=hours_ago(random.randint(2, 96)),
            completed_at=completed_at,
        ))
        for f_type, severity, desc, suggestion in findings:
            db.add(ScribeAuditFinding(
                id=uid("saf_"),
                audit_id=audit_id,
                finding_type=f_type,
                severity=severity,
                description=desc,
                suggested_correction=suggestion,
            ))
    db.commit()
    print(f"    Scribe audits: {len(audits)} created (with findings)")
    return len(audits)


def seed_transparency(db) -> int:
    if already_populated(db, TransparencyRecordModel):
        print("    Transparency: already populated, skipping")
        return 0
    admin = get_admin_id(db)
    records = [
        {
            "id": "tr_sepsis_v2",
            "model_name": "Sepsis Early Warning Model",
            "version": "2.3.1",
            "summary": "An AI tool that predicts the risk of sepsis in adult inpatients using vital signs, labs, and clinical history. Used to alert clinicians early so antibiotic and fluid resuscitation can begin sooner.",
            "intended_population": "Adult inpatients (≥18 years) admitted to ED, ICU, or general medical wards",
            "limitations": "Not validated for pediatric patients, obstetric patients, or post-cardiac-surgery populations. Performance varies across race subgroups (see fairness audit).",
            "perf": {"AUC": 0.872, "sensitivity": 0.81, "PPV": 0.42},
            "regulatory": "FDA 510(k) Cleared (K231847)",
        },
        {
            "id": "tr_readmission_v1",
            "model_name": "30-Day Readmission Risk",
            "version": "1.8.0",
            "summary": "Identifies discharged patients at elevated risk of readmission within 30 days. Used by case management and care coordination teams to prioritize follow-up calls and home-health referrals.",
            "intended_population": "Adult inpatients at hospital discharge",
            "limitations": "Not for use in hospice/comfort-care discharges. Performance disparity observed for Black patients (disparity ratio 0.92, fails 4/5ths rule) — under remediation.",
            "perf": {"AUC": 0.741, "sensitivity": 0.69},
            "regulatory": "Administrative tool — not a medical device",
        },
        {
            "id": "tr_xray_triage_v3",
            "model_name": "Chest X-Ray Triage Classifier",
            "version": "3.0.2",
            "summary": "Prioritizes chest X-rays with critical findings (pneumothorax, large consolidations) to ensure radiologist review happens promptly.",
            "intended_population": "Adult chest X-rays in ED radiology workflow",
            "limitations": "Not validated for pediatric imaging or portable bedside studies under suboptimal conditions. Submitted to FDA — pending clearance.",
            "perf": {"AUC_pneumothorax": 0.94, "AUC_consolidation": 0.88},
            "regulatory": "FDA 510(k) submitted — under review",
        },
    ]
    for r in records:
        rec_id = r["id"]
        created_at = days_ago(random.randint(7, 60))
        db.add(TransparencyRecordModel(
            id=rec_id,
            model_name=r["model_name"],
            model_version=r["version"],
            algorithm_description="Gradient-boosted tree ensemble with calibrated outputs (deep CNN for X-ray)",
            plain_language_summary=r["summary"],
            evidence_base="Internal validation cohort + published clinical literature",
            intended_population=r["intended_population"],
            known_limitations=r["limitations"],
            performance_summary=r["perf"],
            bias_considerations="Subgroup performance documented in linked Bias Audit. See fairness report.",
            regulatory_status=r["regulatory"],
            published_at=created_at + timedelta(days=2),
            version_number=1,
            created_by=admin,
            created_at=created_at,
            updated_at=created_at + timedelta(days=2),
        ))
        # Initial published version snapshot
        db.add(TransparencyVersion(
            id=uid("tv_"),
            record_id=rec_id,
            version_number=1,
            content_snapshot={
                "summary": r["summary"],
                "limitations": r["limitations"],
                "performance": r["perf"],
            },
            change_summary="Initial publication",
            published_by=admin,
            published_at=created_at + timedelta(days=2),
        ))
        # A few acknowledgments per record
        analysts = db.query(User).filter(User.role == UserRole.ANALYST).all()
        for u in analysts[:2]:
            db.add(TransparencyAcknowledgment(
                id=uid("ta_"),
                record_id=rec_id,
                acknowledged_by=u.id,
                acknowledged_at=created_at + timedelta(days=random.randint(3, 30)),
                role_at_time=u.role.value if hasattr(u.role, "value") else str(u.role),
                ip_address_hash=hashlib.sha256(f"10.42.{random.randint(1,255)}.{random.randint(1,255)}".encode()).hexdigest()[:32],
            ))
    db.commit()
    print(f"    Transparency: {len(records)} records (with versions + acknowledgments)")
    return len(records)


def seed_prior_auth(db) -> int:
    if already_populated(db, PriorAuthRecord):
        print("    Prior auth: already populated, skipping")
        return 0
    admin = get_admin_id(db)
    services = [
        ("MRI Lumbar Spine",           [("approve",  "approve", 0.91, None,  None)]),
        ("Cardiac MRI",                [("approve",  "approve", 0.84, None,  None)]),
        ("Bariatric Surgery",          [("deny",     "approve", 0.62, None,  "Surgeon attestation re: failed conservative therapy")]),
        ("Genetic Test (BRCA panel)",  [("approve",  "approve", 0.95, None,  None)]),
        ("PET Scan",                   [("deny",     "deny",    0.81, "INSUFFICIENT_DOC", None)]),
        ("Spinal Cord Stimulator",     [("approve",  "approve", 0.78, None,  None)]),
        ("Colonoscopy (screening)",    [("approve",  "approve", 0.97, None,  None)]),
        ("Inpatient Rehab",            [("deny",     "approve", 0.55, None,  "Therapist override; functional gain documented")]),
        ("Knee MRI",                   [("approve",  "approve", 0.89, None,  None)]),
        ("Cochlear Implant",           [("approve",  "approve", 0.86, None,  None)]),
    ]
    prev_hash = ""
    created = 0
    for service, actions in services:
        for ai_rec, final, conf, denial_reason, override in actions:
            patient_hash = hashlib.sha256(f"patient_{uuid.uuid4()}".encode()).hexdigest()
            claim_id = f"CLM-{random.randint(100000, 999999)}"
            request_dt = days_ago(random.randint(1, 60))
            decision_dt = request_dt + timedelta(days=random.randint(1, 4))
            payload = f"{patient_hash}|{claim_id}|{service}|{final}|{prev_hash}"
            record_hash = hashlib.sha256(payload.encode()).hexdigest()
            db.add(PriorAuthRecord(
                id=uid("pa_"),
                patient_id_hash=patient_hash,
                claim_id=claim_id,
                service_type=service,
                request_date=request_dt.date().isoformat(),
                decision_date=decision_dt.date().isoformat(),
                ai_recommendation=ai_rec,
                ai_confidence=conf,
                human_reviewer_id=admin if override else None,
                human_review_timestamp=decision_dt if override else None,
                final_decision=final,
                denial_reason_code=denial_reason,
                ai_rationale=f"Based on clinical guidelines and {service} payer criteria.",
                override_reason=override,
                prev_record_hash=prev_hash,
                record_hash=record_hash,
                created_at=decision_dt,
            ))
            prev_hash = record_hash
            created += 1
    db.commit()
    print(f"    Prior auth: {created} hash-chained records")
    return created


def seed_revenue_cycle(db) -> int:
    if already_populated(db, RevenueCycleAudit):
        print("    Revenue cycle: already populated, skipping")
        return 0
    admin = get_admin_id(db)
    claims = [
        # claim_id, dx, procedure_codes, billed, expected_range, risk, status, findings
        ("RC-100001", "I50.9",  ["99285", "93010"],         1842.00, {"low": 1500.0, "high": 2100.0}, 0.18, "clean",     []),
        ("RC-100002", "M54.5",  ["72148", "99213"],          985.00, {"low": 800.0,  "high": 1100.0}, 0.21, "clean",     []),
        ("RC-100003", "J18.9",  ["99285", "71046", "99291"],3251.00, {"low": 1900.0, "high": 2400.0}, 0.74, "flagged",
         [("upcoding",         "high",   "99291 (critical care 30-74 min) coded with no documented critical-care criteria", ["99291"], 720.0)]),
        ("RC-100004", "Z34.90", ["59400"],                  4280.00, {"low": 4000.0, "high": 5200.0}, 0.12, "clean",     []),
        ("RC-100005", "K57.92", ["44970", "99231"],         8412.00, {"low": 4800.0, "high": 6500.0}, 0.81, "flagged",
         [("billing_outlier",  "high",   "Charge 35% above 90th percentile for 44970 in this MSA", ["44970"], 1800.0)]),
        ("RC-100006", "E11.9",  ["99214", "83036"],          287.00, {"low": 220.0,  "high": 320.0},  0.08, "clean",     []),
        ("RC-100007", "S82.401A",["27500", "99232"],        7100.00, {"low": 6200.0, "high": 7800.0}, 0.31, "flagged",
         [("modifier_misuse",  "medium", "Modifier 22 applied without documentation of increased complexity", ["27500"], 0.0)]),
        ("RC-100008", "G47.33", ["95810", "99213"],         1620.00, {"low": 1300.0, "high": 1700.0}, 0.15, "clean",     []),
    ]
    for claim_id, dx, procs, billed, expected, risk, status, findings in claims:
        audit_id = uid("rc_")
        created_at = days_ago(random.randint(1, 30))
        db.add(RevenueCycleAudit(
            id=audit_id,
            claim_id=claim_id,
            claim_date=created_at.date().isoformat(),
            provider_id=f"PROV-{random.randint(1000, 9999)}",
            payer_id=random.choice(["BCBS", "AETNA", "UNITED", "MEDICARE", "MEDICAID"]),
            primary_diagnosis_code=dx,
            procedure_codes=procs,
            modifiers=[] if random.random() > 0.3 else ["25"],
            billed_amount=billed,
            expected_amount_range=expected,
            risk_score=risk,
            findings=[{"type": f[0], "severity": f[1]} for f in findings],
            status=status,
            reviewed_by=admin if status == "flagged" else None,
            reviewed_at=created_at + timedelta(days=1) if status == "flagged" else None,
            created_at=created_at,
            updated_at=created_at + timedelta(days=1),
        ))
        for f_type, sev, desc, codes, overbill in findings:
            db.add(RevenueCycleFinding(
                id=uid("rcf_"),
                audit_id=audit_id,
                finding_type=f_type,
                severity=sev,
                description=desc,
                affected_codes=codes,
                estimated_overbilling=overbill,
            ))
    # Coding benchmarks (small set so the API has reference data)
    benchmarks = [
        ("99285", "Emergency Medicine",   850.0, 1100.0, 1450.0, 1850.0),
        ("99291", "Critical Care",        450.0,  650.0,  920.0, 1200.0),
        ("44970", "General Surgery",     4200.0, 5400.0, 6800.0, 8100.0),
        ("27500", "Orthopedic Surgery",  4800.0, 6100.0, 7400.0, 8700.0),
        ("72148", "Radiology",            580.0,  720.0,  890.0, 1050.0),
    ]
    for cpt, specialty, p25, p50, p75, p90 in benchmarks:
        db.add(CodingBenchmark(
            id=uid("cb_"),
            procedure_code=cpt,
            specialty=specialty,
            p25_amount=p25,
            p50_amount=p50,
            p75_amount=p75,
            p90_amount=p90,
            source="CMS-Medicare 2025",
        ))
    db.commit()
    print(f"    Revenue cycle: {len(claims)} audits + {len(benchmarks)} coding benchmarks")
    return len(claims)


def seed_technical_files(db) -> int:
    if already_populated(db, TechnicalFile):
        print("    Technical files: already populated, skipping")
        return 0
    admin = get_admin_id(db)
    files = [
        ("tf_sepsis_510k",        "Sepsis Early Warning Model — 510(k) Submission",         "fda_510k", "Sepsis Early Warning Model", "2.3.1", "approved"),
        ("tf_xray_510k",          "Chest X-Ray Triage Classifier — 510(k) Submission",      "fda_510k", "Chest X-Ray Triage Classifier", "3.0.2", "submitted"),
        ("tf_xray_eu_mdr",        "Chest X-Ray Triage Classifier — EU MDR Technical File",  "eu_mdr",   "Chest X-Ray Triage Classifier", "3.0.2", "draft"),
    ]
    for tf_id, title, reg_type, product, version, stage in files:
        db.add(TechnicalFile(
            id=tf_id,
            title=title,
            regulatory_type=reg_type,
            product_name=product,
            device_version=version,
            lifecycle_stage=stage,
            created_by=admin,
            created_at=days_ago(random.randint(60, 365)),
            updated_at=days_ago(random.randint(0, 30)),
        ))
        sections = [
            ("device_description",     "Device intended for clinical decision support; takes vital signs and labs as input; outputs sepsis risk score 0-1."),
            ("intended_use",           "Adult inpatients in ED, ICU, or general medicine wards. Not for pediatric or OB use."),
            ("performance_data",       json.dumps({"AUC": 0.872, "sensitivity": 0.81, "specificity": 0.83}, indent=2)),
            ("risk_management",        "Risk file references ISO 14971:2019; key residual risks documented in Annex A."),
            ("clinical_evaluation",    "Clinical performance validated in multi-site cohort (n=42K)."),
        ]
        for idx, (sec_type, content) in enumerate(sections):
            db.add(TechnicalFileSection(
                id=uid("tfs_"),
                file_id=tf_id,
                section_type=sec_type,
                content=content,
                order_index=idx,
                auto_generated=(sec_type == "performance_data"),
            ))
        db.add(TechnicalFileVersion(
            id=uid("tfv_"),
            file_id=tf_id,
            version_number=1,
            snapshot_json={"sections": [s[0] for s in sections]},
            created_by=admin,
        ))
    db.commit()
    print(f"    Technical files: {len(files)} created (with sections + version snapshot)")
    return len(files)


def seed_adverse_events(db) -> int:
    if already_populated(db, AdverseEvent):
        print("    Adverse events: already populated, skipping")
        return 0
    events = [
        ("mc_sepsis_predictor",         None,            "false_negative",          "high",     "Patient developed septic shock 6h after sepsis-model risk score remained below alert threshold; review found atypical presentation",                          "ICU admission, 4d hospitalization, full recovery", "investigating"),
        ("mc_readmission_30d",          None,            "fairness_concern",        "medium",   "Bias audit identified disparity ratio 0.92 for Black patients in readmission predictions; remediation in progress",                                            "No direct patient harm; remediation underway",       "investigating"),
        ("mc_chest_xray_triage",        None,            "false_positive_overload", "low",      "AI flagged 12 chest X-rays as critical in 2-hour window — radiologist reported alarm fatigue concern",                                                          "No patient harm; workflow disruption",                "resolved"),
        ("mc_documentation_assistant",  "agent_documentation_assistant",  "hallucination",          "critical", "Scribe AI generated 'denies suicidal ideation' in note when patient transcript did not contain that phrase; clinician caught during review",                  "Caught before signing; no patient harm",             "resolved"),
        ("mc_prior_auth_assistant",     None,            "appeal_overturn",         "low",      "Prior-auth denial overturned on first-level appeal; pattern observed in 8% of denials",                                                                       "Care delay 4 days; no clinical harm",                "open"),
    ]
    for model_id, agent_id, ev_type, severity, desc, impact, status in events:
        reported_at = days_ago(random.randint(2, 120))
        resolved_at = reported_at + timedelta(days=random.randint(2, 21)) if status == "resolved" else None
        db.add(AdverseEvent(
            id=uid("ae_"),
            model_id=model_id,
            agent_id=agent_id,
            event_type=ev_type,
            severity=severity,
            description=desc,
            patient_impact=impact,
            reported_by=get_admin_id(db),
            status=status,
            resolved_at=resolved_at,
            reported_at=reported_at,
            created_at=reported_at,
        ))
    db.commit()
    print(f"    Adverse events: {len(events)} created")
    return len(events)


def seed_pms_reports(db) -> int:
    if already_populated(db, PMSReport):
        print("    PMS reports: already populated, skipping")
        return 0
    admin = get_admin_id(db)
    reports = [
        ("psur",       "published", days_ago(180), days_ago(0), "Periodic Safety Update Report — H1 2026.\nReviewed 5 adverse events (1 critical, 1 high). Bias audit on readmission model identified disparity; remediation initiated. No FDA reportable events.",
         [("adverse_events_count", 5.0, "events"), ("critical_events", 1.0, "events"), ("models_in_production", 4.0, "models"), ("avg_decision_volume_per_day", 12420.0, "decisions")]),
        ("quarterly", "draft",      days_ago(90),  days_ago(0), "Q2 2026 quarterly surveillance report — draft. Awaiting bias audit results for chest X-ray classifier.",
         [("adverse_events_count", 2.0, "events"), ("models_in_production", 4.0, "models"), ("avg_decision_volume_per_day", 13800.0, "decisions")]),
    ]
    for r_type, status, period_start, period_end, summary, metrics in reports:
        report_id = uid("pms_")
        db.add(PMSReport(
            id=report_id,
            report_type=r_type,
            status=status,
            period_start=period_start,
            period_end=period_end,
            summary=summary,
            generated_at=days_ago(random.randint(0, 14)) if status == "published" else None,
            created_by=admin,
            created_at=days_ago(random.randint(0, 30)),
            updated_at=days_ago(random.randint(0, 7)),
        ))
        for name, val, unit in metrics:
            db.add(PMSMetric(
                id=uid("pmsm_"),
                report_id=report_id,
                metric_name=name,
                metric_value=val,
                metric_unit=unit,
            ))
    db.commit()
    print(f"    PMS reports: {len(reports)} created (with metrics)")
    return len(reports)


def seed_risk_scores(db) -> int:
    if already_populated(db, RiskScore):
        print("    Risk scores: already populated, skipping")
        return 0
    created = 0
    for model_id, sev, exp, reg, flags in DEMO_RISK_FACTORS:
        # Latest score
        total = round((sev + exp) * reg, 2)
        score_id = uid("rs_")
        computed = days_ago(random.randint(0, 7))
        db.add(RiskScore(
            id=score_id,
            model_id=model_id,
            severity_score=sev,
            exposure_score=exp,
            regulatory_penalty=reg,
            total_risk=total,
            risk_level=_risk_level(total),
            severity_factors={"patient_safety": round(sev * 0.3, 1), "data_sensitivity": round(sev * 0.25, 1), "model_confidence": round(sev * 0.2, 1), "bias_magnitude": round(sev * 0.15, 1), "drift_magnitude": round(sev * 0.10, 1)},
            exposure_factors={"patient_volume": round(exp * 0.30, 1), "decision_frequency": round(exp * 0.30, 1), "automation_level": round(exp * 0.25, 1), "data_access_breadth": round(exp * 0.15, 1)},
            regulatory_flags=flags,
            org_multiplier=1.0,
            computed_at=computed,
        ))
        # 6 historical points showing trend over last 6 weeks
        prev_total = total - random.uniform(-8, 8)
        for week in range(6, 0, -1):
            week_total = round(max(5.0, min(120.0, prev_total + random.uniform(-3, 3))), 2)
            db.add(RiskScoreHistory(
                id=uid("rsh_"),
                model_id=model_id,
                total_risk=week_total,
                risk_level=_risk_level(week_total),
                delta=round(week_total - prev_total, 2),
                trend="up" if week_total - prev_total >= 1.0 else "down" if week_total - prev_total <= -1.0 else "stable",
                computed_at=days_ago(week * 7),
            ))
            prev_total = week_total
        # Add the latest entry too
        db.add(RiskScoreHistory(
            id=uid("rsh_"),
            model_id=model_id,
            total_risk=total,
            risk_level=_risk_level(total),
            delta=round(total - prev_total, 2),
            trend="up" if total - prev_total >= 1.0 else "down" if total - prev_total <= -1.0 else "stable",
            computed_at=computed,
        ))
        # Regulatory mapping
        for reg_name in flags:
            db.add(RiskRegulatoryMapping(
                id=uid("rrm_"),
                model_id=model_id,
                regulation=reg_name,
                applicable=True,
                created_at=days_ago(30),
            ))
        created += 1
    db.commit()
    print(f"    Risk scores: {created} latest scores + 7-week history per model + regulatory mappings")
    return created


# ───────────────────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("  Sentinel AI — Healthcare Governance Demo Data Seeder")
    print("=" * 72)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Order matters: model_cards must exist before bias_audits FK
        seed_model_cards(db)
        seed_bias_audits(db)
        seed_drift(db)
        seed_hitl(db)
        seed_shadow_ai(db)
        seed_scribe_audits(db)
        seed_transparency(db)
        seed_prior_auth(db)
        seed_revenue_cycle(db)
        seed_technical_files(db)
        seed_adverse_events(db)
        seed_pms_reports(db)
        seed_risk_scores(db)

        print()
        print("=" * 72)
        print("  [OK] Healthcare governance demo data seeded successfully!")
        print("=" * 72)
        print()
        print("  Refresh the dashboard — every clinical/admin/finance/regulatory/risk")
        print("  page should now show realistic populated data.")
        print()
    except Exception as e:
        print(f"\n  ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
