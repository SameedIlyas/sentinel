"""CHAI Model Card Auto-Fill Service — orchestrates GitHub + MLflow data."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from policy_engine.services.github_integration import GitHubIntegrationService
from policy_engine.services.mlflow_integration import MLflowIntegrationService

logger = logging.getLogger(__name__)

# Clinical keywords used to infer clinical indications from repo topics
CLINICAL_KEYWORDS = {
    "radiology", "pathology", "oncology", "cardiology", "ehr", "emr",
    "imaging", "diagnosis", "prognosis", "screening", "triage",
    "clinical", "medical", "patient", "disease", "cancer", "tumor",
}


class ModelCardAutoFillRequest(BaseModel):
    repo_url: str
    mlflow_run_id: Optional[str] = None
    experiment_id: Optional[str] = None


class ModelCardAutoFillResult(BaseModel):
    pre_filled: Dict[str, Any]
    requires_human_review: List[str]


class ModelCardAutoFillService:
    """
    Orchestrates GitHub + MLflow data into CHAI model card sections.

    Contraindications are ALWAYS flagged for human review — never auto-filled.
    """

    def __init__(
        self,
        github_service: GitHubIntegrationService,
        mlflow_service: MLflowIntegrationService,
    ) -> None:
        self._github = github_service
        self._mlflow = mlflow_service

    async def auto_fill(
        self, request: ModelCardAutoFillRequest
    ) -> ModelCardAutoFillResult:
        pre_filled: Dict[str, Any] = {}
        requires_human_review: List[str] = ["contraindications"]  # always

        # ── GitHub data ───────────────────────────────────────────────────
        try:
            repo = await self._github.get_repo_metadata(request.repo_url)
            owner, repo_name = repo.owner, repo.repo

            # intended_use: description + topics
            parts = []
            if repo.description:
                parts.append(repo.description)
            if repo.topics:
                parts.append(f"Topics: {', '.join(repo.topics)}")
            if parts:
                pre_filled["intended_use"] = " | ".join(parts)

            # clinical_indications: topics matching clinical keywords
            clinical_topics = [
                t for t in repo.topics
                if t.lower() in CLINICAL_KEYWORDS
            ]
            if clinical_topics:
                pre_filled["clinical_indications"] = ", ".join(clinical_topics)
            else:
                requires_human_review.append("clinical_indications")

            # last_updated: from GitHub push date
            if repo.last_push_at:
                pre_filled["last_updated"] = repo.last_push_at

            # version_history: last 10 commits summarised
            commits = await self._github.get_recent_commits(
                owner, repo_name, limit=10
            )
            if commits:
                pre_filled["version_history"] = [
                    {"sha": c.sha, "message": c.message,
                     "author": c.author, "date": c.date}
                    for c in commits
                ]

        except Exception as exc:  # noqa: BLE001
            logger.warning("GitHub fetch failed during auto-fill: %s", exc)
            requires_human_review.extend(
                ["intended_use", "clinical_indications",
                 "last_updated", "version_history"]
            )

        # ── MLflow data ───────────────────────────────────────────────────
        if self._mlflow.is_configured() and (
            request.mlflow_run_id or request.experiment_id
        ):
            try:
                metrics = await self._mlflow.get_model_metrics(
                    experiment_id=request.experiment_id or "",
                    run_id=request.mlflow_run_id,
                )
                if metrics:
                    perf: Dict[str, Any] = {}
                    for key in ("accuracy", "precision", "recall", "f1", "auc"):
                        val = getattr(metrics, key)
                        if val is not None:
                            perf[key] = val
                    if metrics.custom:
                        perf.update(metrics.custom)
                    if perf:
                        pre_filled["performance_metrics"] = perf

                    # subgroup_performance: metrics with demographic tags
                    subgroup = {
                        k: v for k, v in metrics.custom.items()
                        if any(
                            tag in k.lower()
                            for tag in ("age", "sex", "gender", "race",
                                        "ethnicity", "subgroup")
                        )
                    }
                    if subgroup:
                        pre_filled["subgroup_performance"] = subgroup

                if request.mlflow_run_id:
                    params = await self._mlflow.get_model_parameters(
                        request.mlflow_run_id
                    )
                    if params:
                        pre_filled["training_data_description"] = params

            except Exception as exc:  # noqa: BLE001
                logger.warning("MLflow fetch failed during auto-fill: %s", exc)
                requires_human_review.extend(
                    ["performance_metrics", "training_data_description"]
                )
        else:
            # MLflow not configured — flag for human review
            requires_human_review.extend(
                ["performance_metrics", "training_data_description"]
            )

        # Deduplicate while preserving order
        seen: set = set()
        unique_review: List[str] = []
        for item in requires_human_review:
            if item not in seen:
                seen.add(item)
                unique_review.append(item)

        return ModelCardAutoFillResult(
            pre_filled=pre_filled,
            requires_human_review=unique_review,
        )
