"""MLflow → ModelCard auto-sync service.

Tier 2 Sprint 2 — when a model is registered or a new version is published in
MLflow, a draft ModelCard is created automatically so the governance team
sees the model the same hour it lands. Eliminates the gap between "what we
have running" and "what is documented."

Behaviour:
  - Polls MLflow `/api/2.0/mlflow/registered-models/list` on a configurable
    interval (default 1 hour, gated by `MLFLOW_AUTO_SYNC=true`).
  - For every registered model + version that we don't yet have a
    ModelCard for: creates a draft, links the artifact URI from MLflow,
    populates `monitoring_plan.cadence='hourly'`, and seeds a
    HITL "needs_review" review for the model owner.
  - Idempotent: re-running for an already-synced version is a no-op.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import httpx

from sqlalchemy.orm import Session

from policy_engine.database import SessionLocal
from policy_engine.models.model_card import ModelCard, ModelCardVersion
from policy_engine.services.hitl_auto_service import create_hitl_review
from policy_engine.services.url_validator import validate_external_url

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _env_flag(name: str, default: bool = False) -> bool:
    """Parse an env var as a boolean flag."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def is_enabled() -> bool:
    return _env_flag("MLFLOW_AUTO_SYNC", default=False)


def sync_interval_seconds() -> float:
    """Read MLFLOW_AUTO_SYNC_INTERVAL_SECONDS env var (default 3600)."""
    raw = os.environ.get("MLFLOW_AUTO_SYNC_INTERVAL_SECONDS", "3600")
    try:
        value = float(raw)
        return max(60.0, value)  # clamp to at least 60s to avoid hammering MLflow
    except (TypeError, ValueError):
        return 3600.0


# ---------------------------------------------------------------------------
# MLflow REST client (sync, for use inside scheduler thread)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegisteredModelVersion:
    """A single MLflow registered-model version."""
    name: str
    version: str
    source: Optional[str]              # e.g. "mlflow://runs/abc/model" or s3 path
    run_id: Optional[str]
    description: Optional[str]
    creation_timestamp_ms: Optional[int]
    tags: Dict[str, str]


class MLflowRegistryClient:
    """Read-only MLflow Registry client for the auto-sync job."""

    def __init__(
        self,
        tracking_uri: Optional[str],
        timeout_seconds: float = 10.0,
    ) -> None:
        self._tracking_uri = (
            validate_external_url(tracking_uri) if tracking_uri else None
        )
        self._timeout = httpx.Timeout(timeout_seconds)

    def is_configured(self) -> bool:
        return self._tracking_uri is not None

    def list_registered_models(self) -> List[Dict[str, Any]]:
        """Return all registered models from MLflow (paginated under the hood).

        Empty list when MLflow is unreachable or not configured.
        """
        if not self._tracking_uri:
            return []

        models: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        url = f"{self._tracking_uri}/api/2.0/mlflow/registered-models/search"

        with httpx.Client(timeout=self._timeout) as client:
            for _ in range(20):  # safety: at most 20 pages
                params = {"max_results": 200}
                if page_token:
                    params["page_token"] = page_token
                try:
                    resp = client.get(url, params=params)
                except httpx.HTTPError as exc:
                    logger.warning("MLflow list_registered_models failed: %s", exc)
                    return models
                if not resp.is_success:
                    logger.warning(
                        "MLflow list_registered_models returned %s: %s",
                        resp.status_code, resp.text[:200],
                    )
                    return models
                payload = resp.json()
                models.extend(payload.get("registered_models", []))
                page_token = payload.get("next_page_token")
                if not page_token:
                    break
        return models

    def list_model_versions(self, model_name: str) -> List[RegisteredModelVersion]:
        """Return every version of a registered model."""
        if not self._tracking_uri:
            return []
        url = f"{self._tracking_uri}/api/2.0/mlflow/model-versions/search"
        # MLflow's filter syntax — escape single quotes in model names
        safe_name = model_name.replace("'", "\\'")
        params = {
            "filter": f"name='{safe_name}'",
            "max_results": 200,
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, params=params)
        except httpx.HTTPError as exc:
            logger.warning("MLflow list_model_versions failed for %s: %s", model_name, exc)
            return []
        if not resp.is_success:
            return []

        results: List[RegisteredModelVersion] = []
        for v in resp.json().get("model_versions", []):
            tags = {
                t.get("key"): t.get("value")
                for t in v.get("tags", [])
                if t.get("key")
            }
            results.append(RegisteredModelVersion(
                name=v.get("name", model_name),
                version=str(v.get("version", "1")),
                source=v.get("source"),
                run_id=v.get("run_id"),
                description=v.get("description"),
                creation_timestamp_ms=v.get("creation_timestamp"),
                tags=tags,
            ))
        return results


# ---------------------------------------------------------------------------
# Sync job
# ---------------------------------------------------------------------------

@dataclass
class SyncOutcome:
    """What happened during one sync pass — useful for tests + ops dashboards."""
    seen_models: int = 0
    seen_versions: int = 0
    cards_created: int = 0
    versions_recorded: int = 0
    hitl_reviews_created: int = 0
    errors: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def _draft_card_from_mlflow(
    rmv: RegisteredModelVersion,
    *,
    organization_id: Optional[str],
) -> ModelCard:
    """Build a minimal CHAI draft ModelCard from MLflow metadata."""
    now = datetime.utcnow()
    return ModelCard(
        id=str(uuid.uuid4()),
        name=rmv.name,
        version=rmv.version,
        lifecycle_stage="draft",
        intended_use=rmv.description or None,
        clinical_indications=None,
        contraindications=None,
        training_data_source=rmv.tags.get("training_data_source"),
        performance_metrics={},
        bias_summary={},
        fda_status=rmv.tags.get("fda_status"),
        chai_version="2.0",
        organization_id=organization_id or rmv.tags.get("organization_id"),
        model_artifact_uri=rmv.source,
        training_dataset_sha256=rmv.tags.get("training_dataset_sha256"),
        evaluation_dataset_sha256=rmv.tags.get("evaluation_dataset_sha256"),
        git_commit_sha=rmv.tags.get("git_commit_sha") or rmv.run_id,
        framework_version=rmv.tags.get("framework_version"),
        external_validation={},
        monitoring_plan={"cadence": "hourly", "source": "mlflow_auto_sync"},
        pccp={},
        created_by=f"system:mlflow_auto_sync",
        created_at=now,
        updated_at=now,
    )


def _existing_card_for_version(
    db: Session, name: str, version: str
) -> Optional[ModelCard]:
    return (
        db.query(ModelCard)
        .filter(ModelCard.name == name, ModelCard.version == version)
        .first()
    )


def sync_once(
    *,
    client: MLflowRegistryClient,
    db_factory: Optional[Any] = None,
    organization_id: Optional[str] = None,
) -> SyncOutcome:
    """Run a single MLflow → ModelCard sync pass. Idempotent.

    Args:
        client: An MLflowRegistryClient (configured or not).
        db_factory: Callable returning a Session (for tests). Defaults to
            policy_engine.database.SessionLocal.
        organization_id: Default organization to attach to created cards.

    Returns:
        SyncOutcome with per-pass statistics.
    """
    outcome = SyncOutcome()

    if not client.is_configured():
        logger.info("MLflow auto-sync skipped: tracking_uri not configured")
        return outcome

    db_factory = db_factory or SessionLocal
    db = db_factory()
    try:
        registered = client.list_registered_models()
        outcome.seen_models = len(registered)

        for entry in registered:
            name = entry.get("name")
            if not name:
                continue
            versions = client.list_model_versions(name)
            outcome.seen_versions += len(versions)

            for rmv in versions:
                try:
                    existing = _existing_card_for_version(db, rmv.name, rmv.version)
                    if existing is not None:
                        # Already known — make sure the lineage URI is up to date
                        if (
                            rmv.source
                            and existing.model_artifact_uri != rmv.source
                        ):
                            existing.model_artifact_uri = rmv.source
                            existing.updated_at = datetime.utcnow()
                            db.commit()
                        continue

                    card = _draft_card_from_mlflow(
                        rmv, organization_id=organization_id
                    )
                    db.add(card)
                    db.flush()

                    db.add(ModelCardVersion(
                        id=str(uuid.uuid4()),
                        model_card_id=card.id,
                        version_number=card.version,
                        content={
                            "source": "mlflow_auto_sync",
                            "mlflow_run_id": rmv.run_id,
                            "mlflow_source": rmv.source,
                            "tags": rmv.tags,
                        },
                        published_by="system:mlflow_auto_sync",
                        published_at=datetime.utcnow(),
                        changelog=(
                            "Auto-imported from MLflow Model Registry. "
                            "Governance review required before publish."
                        ),
                    ))
                    db.commit()
                    outcome.cards_created += 1
                    outcome.versions_recorded += 1

                    review_id = create_hitl_review(
                        db,
                        title=f"New model in MLflow: {rmv.name} v{rmv.version}",
                        description=(
                            f"MLflow auto-sync detected a new model version. "
                            f"A draft card has been created (id={card.id}). "
                            "Please complete CHAI sections and assign reviewers "
                            "before publishing."
                        ),
                        ai_decision={
                            "source": "mlflow_auto_sync",
                            "model_card_id": card.id,
                            "model_name": rmv.name,
                            "model_version": rmv.version,
                            "mlflow_run_id": rmv.run_id,
                        },
                        risk_score=20.0,
                        priority="medium",
                        organization_id=card.organization_id,
                        actor_id="system:mlflow_auto_sync",
                        seed_action="mlflow_new_model",
                    )
                    if review_id:
                        outcome.hitl_reviews_created += 1

                    logger.info(
                        "MLflow auto-sync created card: id=%s name=%s version=%s",
                        card.id, rmv.name, rmv.version,
                    )

                except Exception as exc:
                    msg = f"failed model={name} version={rmv.version}: {exc}"
                    outcome.errors.append(msg)
                    logger.error("MLflow auto-sync %s", msg, exc_info=True)
                    try:
                        db.rollback()
                    except Exception:
                        pass

    finally:
        db.close()

    logger.info(
        "MLflow auto-sync pass complete: models=%d versions=%d created=%d hitl=%d errors=%d",
        outcome.seen_models, outcome.seen_versions, outcome.cards_created,
        outcome.hitl_reviews_created, len(outcome.errors),
    )
    return outcome


# ---------------------------------------------------------------------------
# Entry point used by the scheduler at startup
# ---------------------------------------------------------------------------

def make_sync_job(
    *, tracking_uri: Optional[str], organization_id: Optional[str] = None
):
    """Build a zero-arg sync callable suitable for the scheduler."""
    client = MLflowRegistryClient(tracking_uri=tracking_uri)

    def _job() -> None:
        try:
            sync_once(client=client, organization_id=organization_id)
        except Exception as exc:
            logger.error("MLflow auto-sync job failed: %s", exc, exc_info=True)

    return _job
