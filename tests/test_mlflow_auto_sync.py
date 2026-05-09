"""Tests for MLflow auto-sync (Tier 2 Sprint 2 task #3)."""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from policy_engine.models.hitl import HITLReview
from policy_engine.models.model_card import ModelCard, ModelCardVersion
from policy_engine.services.mlflow_auto_sync import (
    MLflowRegistryClient,
    RegisteredModelVersion,
    is_enabled,
    sync_interval_seconds,
    sync_once,
)


# ---------------------------------------------------------------------------
# Stub client used in tests so we never hit the network
# ---------------------------------------------------------------------------

class _StubClient(MLflowRegistryClient):
    def __init__(
        self,
        models: List[Dict[str, Any]],
        versions_by_name: Dict[str, List[RegisteredModelVersion]],
    ) -> None:
        # Skip parent __init__ to avoid SSRF validation on a fake URL
        self._tracking_uri = "http://stub.local"
        self._timeout = None  # not used
        self._models = models
        self._versions = versions_by_name

    def is_configured(self) -> bool:
        return True

    def list_registered_models(self) -> List[Dict[str, Any]]:
        return self._models

    def list_model_versions(self, model_name: str) -> List[RegisteredModelVersion]:
        return self._versions.get(model_name, [])


def _factory(db_session):
    """Return a callable yielding the test session each time it's invoked."""
    def _get_db():
        return db_session
    return _get_db


def _patch_session_close(db_session, monkeypatch):
    """Stop sync_once from closing our test session."""
    monkeypatch.setattr(db_session, "close", lambda: None)


def test_is_enabled_reads_env(monkeypatch):
    monkeypatch.delenv("MLFLOW_AUTO_SYNC", raising=False)
    assert is_enabled() is False
    monkeypatch.setenv("MLFLOW_AUTO_SYNC", "true")
    assert is_enabled() is True
    monkeypatch.setenv("MLFLOW_AUTO_SYNC", "0")
    assert is_enabled() is False


def test_sync_interval_clamps_below_60_seconds(monkeypatch):
    monkeypatch.setenv("MLFLOW_AUTO_SYNC_INTERVAL_SECONDS", "5")
    assert sync_interval_seconds() == 60.0
    monkeypatch.setenv("MLFLOW_AUTO_SYNC_INTERVAL_SECONDS", "1800")
    assert sync_interval_seconds() == 1800.0


def test_sync_once_creates_card_for_new_mlflow_version(db_session, monkeypatch):
    _patch_session_close(db_session, monkeypatch)

    client = _StubClient(
        models=[{"name": "sepsis-ew"}],
        versions_by_name={
            "sepsis-ew": [
                RegisteredModelVersion(
                    name="sepsis-ew",
                    version="1",
                    source="mlflow://runs/abc/model",
                    run_id="abc",
                    description="Sepsis early warning model",
                    creation_timestamp_ms=1700000000000,
                    tags={
                        "training_data_source": "MIMIC-IV",
                        "fda_status": "510(k) cleared",
                    },
                )
            ]
        },
    )

    outcome = sync_once(
        client=client,
        db_factory=_factory(db_session),
        organization_id="org-test",
    )

    assert outcome.cards_created == 1
    assert outcome.versions_recorded == 1
    assert outcome.hitl_reviews_created == 1
    assert outcome.errors == []

    cards = db_session.query(ModelCard).all()
    assert len(cards) == 1
    card = cards[0]
    assert card.name == "sepsis-ew"
    assert card.version == "1"
    assert card.lifecycle_stage == "draft"
    assert card.model_artifact_uri == "mlflow://runs/abc/model"
    assert card.training_data_source == "MIMIC-IV"
    assert card.fda_status == "510(k) cleared"
    assert card.organization_id == "org-test"
    assert card.monitoring_plan == {"cadence": "hourly", "source": "mlflow_auto_sync"}

    versions = db_session.query(ModelCardVersion).all()
    assert len(versions) == 1
    assert versions[0].content["source"] == "mlflow_auto_sync"
    assert versions[0].content["mlflow_run_id"] == "abc"

    reviews = db_session.query(HITLReview).all()
    assert len(reviews) == 1
    assert "sepsis-ew" in reviews[0].title
    assert reviews[0].priority == "medium"
    assert reviews[0].ai_decision["model_card_id"] == card.id


def test_sync_once_is_idempotent_for_same_version(db_session, monkeypatch):
    _patch_session_close(db_session, monkeypatch)

    rmv = RegisteredModelVersion(
        name="m1", version="1",
        source="mlflow://runs/r1/model",
        run_id="r1", description="m1",
        creation_timestamp_ms=None, tags={},
    )
    client = _StubClient(
        models=[{"name": "m1"}],
        versions_by_name={"m1": [rmv]},
    )

    first = sync_once(client=client, db_factory=_factory(db_session))
    second = sync_once(client=client, db_factory=_factory(db_session))

    assert first.cards_created == 1
    assert second.cards_created == 0
    assert db_session.query(ModelCard).count() == 1


def test_sync_once_updates_artifact_uri_when_changed(db_session, monkeypatch):
    _patch_session_close(db_session, monkeypatch)

    rmv_v1 = RegisteredModelVersion(
        name="m1", version="1",
        source="mlflow://runs/old/model",
        run_id="old", description=None, creation_timestamp_ms=None, tags={},
    )
    client_v1 = _StubClient(models=[{"name": "m1"}], versions_by_name={"m1": [rmv_v1]})
    sync_once(client=client_v1, db_factory=_factory(db_session))

    rmv_v1_new_source = RegisteredModelVersion(
        name="m1", version="1",
        source="mlflow://runs/new/model",
        run_id="old", description=None, creation_timestamp_ms=None, tags={},
    )
    client_v2 = _StubClient(
        models=[{"name": "m1"}], versions_by_name={"m1": [rmv_v1_new_source]}
    )
    second = sync_once(client=client_v2, db_factory=_factory(db_session))

    assert second.cards_created == 0  # same name+version
    card = db_session.query(ModelCard).filter_by(name="m1", version="1").first()
    assert card.model_artifact_uri == "mlflow://runs/new/model"


def test_sync_once_creates_card_per_version(db_session, monkeypatch):
    _patch_session_close(db_session, monkeypatch)

    versions = [
        RegisteredModelVersion(
            name="m1", version="1",
            source="mlflow://runs/v1", run_id="r1",
            description=None, creation_timestamp_ms=None, tags={},
        ),
        RegisteredModelVersion(
            name="m1", version="2",
            source="mlflow://runs/v2", run_id="r2",
            description=None, creation_timestamp_ms=None, tags={},
        ),
    ]
    client = _StubClient(models=[{"name": "m1"}], versions_by_name={"m1": versions})

    outcome = sync_once(client=client, db_factory=_factory(db_session))

    assert outcome.cards_created == 2
    assert db_session.query(ModelCard).filter_by(name="m1").count() == 2


def test_sync_once_skips_when_unconfigured(db_session, monkeypatch):
    _patch_session_close(db_session, monkeypatch)

    class _Unconfigured(_StubClient):
        def is_configured(self) -> bool:
            return False

    client = _Unconfigured(models=[], versions_by_name={})
    outcome = sync_once(client=client, db_factory=_factory(db_session))

    assert outcome.seen_models == 0
    assert outcome.cards_created == 0
