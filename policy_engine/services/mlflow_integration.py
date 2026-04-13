"""MLflow Integration Service for CHAI model card auto-fill."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
from policy_engine.services.url_validator import SSRFBlockedError, validate_external_url

logger = logging.getLogger(__name__)


@dataclass
class ModelMetrics:
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    auc: Optional[float] = None
    custom: Dict[str, float] = field(default_factory=dict)


@dataclass
class ArtifactSummary:
    name: str   # PHI-redacted
    size_bytes: Optional[int]


class MLflowIntegrationService:
    """Fetches model metrics and parameters from MLflow for model card auto-fill."""

    def __init__(
        self,
        tracking_uri: Optional[str] = None,
        timeout_seconds: int = 10,
    ) -> None:
        self._phi_engine = PHIRedactionEngine()
        self._timeout = httpx.Timeout(
            connect=5.0, read=float(timeout_seconds), write=5.0, pool=5.0
        )
        self._tracking_uri: Optional[str] = None
        if tracking_uri:
            # Validate SSRF safety once at construction — not per-call
            self._tracking_uri = validate_external_url(tracking_uri)

    def is_configured(self) -> bool:
        return self._tracking_uri is not None

    async def get_model_metrics(
        self, experiment_id: str, run_id: Optional[str] = None
    ) -> Optional[ModelMetrics]:
        """Return accuracy/AUC/etc from MLflow. None if MLflow not configured."""
        if not self._tracking_uri:
            return None
        if run_id:
            data = await self._get_run(run_id)
        else:
            data = await self._search_runs(experiment_id)
        if data is None:
            return None
        return self._parse_metrics(data)

    async def get_model_parameters(self, run_id: str) -> Optional[Dict[str, str]]:
        """Return training parameters for a run. None if MLflow not configured."""
        if not self._tracking_uri:
            return None
        data = await self._get_run(run_id)
        if data is None:
            return None
        params = data.get("data", {}).get("params", [])
        return {p["key"]: p["value"] for p in params}

    async def get_model_artifacts(self, run_id: str) -> Optional[List[ArtifactSummary]]:
        """Return artifact names (PHI-redacted) and sizes. None if not configured."""
        if not self._tracking_uri:
            return None
        url = f"{self._tracking_uri}/api/2.0/mlflow/artifacts/list"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, params={"run_id": run_id})
        if not response.is_success:
            return None
        files = response.json().get("files", [])
        results: List[ArtifactSummary] = []
        for f in files:
            raw_name = f.get("path", "")
            safe_name = self._phi_engine.redact(raw_name).redacted_text
            results.append(
                ArtifactSummary(
                    name=safe_name,
                    size_bytes=f.get("file_size"),
                )
            )
        return results

    # ── private helpers ────────────────────────────────────────────────────

    async def _get_run(self, run_id: str) -> Optional[dict]:
        url = f"{self._tracking_uri}/api/2.0/mlflow/runs/get"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, params={"run_id": run_id})
        if not response.is_success:
            return None
        return response.json().get("run")

    async def _search_runs(self, experiment_id: str) -> Optional[dict]:
        url = f"{self._tracking_uri}/api/2.0/mlflow/runs/search"
        payload = {
            "experiment_ids": [experiment_id],
            "max_results": 1,
            "order_by": ["start_time DESC"],
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload)
        if not response.is_success:
            return None
        runs = response.json().get("runs", [])
        return runs[0] if runs else None

    def _parse_metrics(self, run_data: dict) -> ModelMetrics:
        raw = {
            m["key"]: m["value"]
            for m in run_data.get("data", {}).get("metrics", [])
        }
        custom = {
            k: v for k, v in raw.items()
            if k not in ("accuracy", "precision", "recall", "f1", "auc")
        }
        return ModelMetrics(
            accuracy=raw.get("accuracy"),
            precision=raw.get("precision"),
            recall=raw.get("recall"),
            f1=raw.get("f1"),
            auc=raw.get("auc"),
            custom=custom,
        )
