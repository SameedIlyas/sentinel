"""Regression test for CRIT-010 — migration 020 makes organization_id NOT NULL.

Two contracts the migration enforces:

1. **Safety**: surveys orphan rows first and refuses to run if any are
   found. Operators must run ``scripts/backfill_organization_id.py``
   and re-run the migration.

2. **Models match the schema**: every model in the target list reports
   ``nullable=False`` once the migration has applied so application
   code can rely on the contract.

This is a static contract test: we load the migration module and
assert that the upgrade() body contains the survey logic and the
ALTER COLUMN sweep. A full alembic round-trip belongs in the W-2
Postgres CI lane.
"""
from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "2026_05_19_0000-020_org_id_not_null.py"
)


REQUIRED_TABLES = (
    "audit_logs",
    "alerts",
    "prior_auth_records",
    "hitl_reviews",
    "shadow_ai_detections",
    "scribe_audits",
    "model_cards",
    "bias_audits",
    "revenue_cycle_audits",
    "risk_scores",
    "clinic_ai_tools",
    "clinic_ai_observations",
    "clinic_report_artifacts",
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig_020", MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("table", REQUIRED_TABLES)
def test_upgrade_targets_each_table(table: str) -> None:
    mod = _load_migration()
    source = inspect.getsource(mod)
    assert table in source, (
        f"Migration 020 does not include table {table!r} in its target list"
    )


def test_upgrade_surveys_nulls_before_altering() -> None:
    """Safety: must survey for NULL rows before any ALTER COLUMN."""
    mod = _load_migration()
    source = inspect.getsource(mod.upgrade)
    assert "_survey_nulls" in source or "IS NULL" in source, (
        "Upgrade must survey NULL counts before issuing ALTER COLUMN"
    )


def test_upgrade_refuses_on_orphans() -> None:
    """If a survey shows orphans the migration must raise, not silently apply."""
    mod = _load_migration()
    source = inspect.getsource(mod.upgrade)
    assert "RuntimeError" in source or "raise" in source, (
        "Upgrade must raise when orphan rows are found"
    )


def test_downgrade_is_nondestructive() -> None:
    mod = _load_migration()
    source = inspect.getsource(mod.downgrade)
    # Downgrade only flips nullability back. No DROP or DELETE.
    assert "DROP TABLE" not in source.upper()
    assert "DELETE FROM" not in source.upper()


# ---------------------------------------------------------------------------
# Model contract — each model exposes nullable=False after the migration
# ---------------------------------------------------------------------------

_MODEL_PATHS = {
    "audit_logs": "policy_engine.models.audit_log:AuditLog",
    "alerts": "policy_engine.models.alert:Alert",
    "prior_auth_records": "policy_engine.models.prior_auth:PriorAuthRecord",
    "hitl_reviews": "policy_engine.models.hitl:HITLReview",
    "shadow_ai_detections": "policy_engine.models.shadow_ai:ShadowAIDetectionModel",
    "scribe_audits": "policy_engine.models.scribe_audit:ScribeAuditModel",
    "model_cards": "policy_engine.models.model_card:ModelCard",
    "bias_audits": "policy_engine.models.bias_audit:BiasAuditModel",
    "revenue_cycle_audits": "policy_engine.models.revenue_cycle:RevenueCycleAudit",
    "risk_scores": "policy_engine.models.risk_score:RiskScore",
    # clinic_* models use `org_id` not `organization_id` — checked
    # separately below where the column name differs.
}


@pytest.mark.parametrize("table,model_path", _MODEL_PATHS.items())
def test_model_organization_id_nullable_false(table: str, model_path: str) -> None:
    """After this PR lands, every named model must have organization_id NOT NULL."""
    module_path, class_name = model_path.split(":")
    mod = __import__(module_path, fromlist=[class_name])
    model = getattr(mod, class_name)
    col = model.__table__.columns.get("organization_id")
    assert col is not None, f"{class_name}.organization_id missing"
    assert col.nullable is False, (
        f"{class_name}.organization_id must be NOT NULL after CRIT-010"
    )


_CLINIC_MODEL_PATHS = {
    "clinic_ai_tools": "policy_engine.models.clinic:ClinicAiTool",
    "clinic_ai_observations": "policy_engine.models.clinic:ClinicAiObservation",
    "clinic_report_artifacts": "policy_engine.models.clinic:ClinicReportArtifact",
}


@pytest.mark.parametrize("table,model_path", _CLINIC_MODEL_PATHS.items())
def test_clinic_model_org_id_nullable_false(table: str, model_path: str) -> None:
    module_path, class_name = model_path.split(":")
    mod = __import__(module_path, fromlist=[class_name])
    model = getattr(mod, class_name)
    col = model.__table__.columns.get("org_id")
    assert col is not None, f"{class_name}.org_id missing"
    assert col.nullable is False, (
        f"{class_name}.org_id must be NOT NULL after CRIT-010"
    )
