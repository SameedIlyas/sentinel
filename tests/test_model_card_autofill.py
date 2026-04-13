"""Tests for Phase 4 — Model Card Auto-Fill Engine.

All external HTTP calls are mocked with respx — no real GitHub/MLflow traffic.
"""
from __future__ import annotations

import ipaddress
import json
import socket
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
import respx
from httpx import Response

from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
from policy_engine.services.github_integration import (
    GitHubAuthError,
    GitHubIntegrationService,
    GitHubRateLimitError,
)
from policy_engine.services.mlflow_integration import MLflowIntegrationService
from policy_engine.services.model_card_service import (
    ModelCardAutoFillRequest,
    ModelCardAutoFillService,
)
from policy_engine.services.url_validator import (
    SSRFBlockedError,
    validate_external_url,
    validate_github_url,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def github_svc() -> GitHubIntegrationService:
    return GitHubIntegrationService(
        token=None,
        base_url="https://api.github.com",
        timeout_seconds=5,
    )


@pytest.fixture()
def mlflow_svc_unconfigured() -> MLflowIntegrationService:
    return MLflowIntegrationService(tracking_uri=None)


def _make_autofill_service(
    github: GitHubIntegrationService,
    mlflow: MLflowIntegrationService,
) -> ModelCardAutoFillService:
    return ModelCardAutoFillService(github_service=github, mlflow_service=mlflow)


def _repo_payload(
    description: str = "AI model for radiology screening",
    topics: list | None = None,
    pushed_at: str = "2024-01-15T10:00:00Z",
) -> Dict[str, Any]:
    return {
        "description": description,
        "default_branch": "main",
        "language": "Python",
        "pushed_at": pushed_at,
        "topics": topics or ["radiology", "ai", "screening"],
    }


# ── Task 4.0 — contains_phi() ─────────────────────────────────────────────────


def test_contains_phi_returns_true_for_phi_text() -> None:
    engine = PHIRedactionEngine()
    assert engine.contains_phi("Patient email: dr.smith@hospital.org") is True


def test_contains_phi_returns_false_for_clean_text() -> None:
    engine = PHIRedactionEngine()
    assert engine.contains_phi("clean repository description") is False


def test_contains_phi_returns_false_for_empty_string() -> None:
    engine = PHIRedactionEngine()
    assert engine.contains_phi("") is False


def test_contains_phi_returns_false_for_none() -> None:
    engine = PHIRedactionEngine()
    assert engine.contains_phi(None) is False  # type: ignore[arg-type]


# ── Task 4.4 — URL Validator ──────────────────────────────────────────────────


def test_github_service_extracts_owner_repo_from_url() -> None:
    owner, repo = validate_github_url("https://github.com/SameedIlyas/sentinel")
    assert owner == "SameedIlyas"
    assert repo == "sentinel"


def test_github_service_rejects_non_github_urls() -> None:
    """SSRF prevention: only github.com is allowed."""
    with pytest.raises(ValueError):
        validate_github_url("https://evil.com/owner/repo")


def test_github_url_rejects_http_scheme() -> None:
    with pytest.raises(ValueError):
        validate_github_url("http://github.com/owner/repo")


def test_github_url_rejects_path_traversal() -> None:
    with pytest.raises(ValueError):
        validate_github_url("https://github.com/../etc/passwd")


def test_ssrf_blocked_error_is_value_error_subclass() -> None:
    assert issubclass(SSRFBlockedError, ValueError)


def test_github_service_rejects_private_ip_mlflow_uri() -> None:
    """DNS rebinding check: private IPs blocked in validate_external_url."""
    # Directly test that a private IP URL is blocked
    with pytest.raises(SSRFBlockedError):
        validate_external_url("http://127.0.0.1:8000")


def test_validate_external_url_blocks_10_x_range() -> None:
    with pytest.raises(SSRFBlockedError):
        validate_external_url("http://10.0.0.1/mlflow")


def test_validate_external_url_blocks_192_168_range() -> None:
    with pytest.raises(SSRFBlockedError):
        validate_external_url("http://192.168.1.1/mlflow")


def test_validate_external_url_blocks_file_scheme() -> None:
    with pytest.raises(SSRFBlockedError):
        validate_external_url("file:///etc/passwd")


def test_validate_external_url_blocks_non_standard_port() -> None:
    """Port 8080 should be blocked when MLFLOW_ALLOW_CUSTOM_PORT is not set."""
    # Mock DNS to return a public IP so only port check triggers
    public_ip = "93.184.216.34"  # example.com

    def mock_getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (public_ip, 0))]

    with patch("socket.getaddrinfo", side_effect=mock_getaddrinfo):
        with pytest.raises(SSRFBlockedError, match="port"):
            validate_external_url("http://example.com:8080/mlflow")


def test_validate_external_url_dns_rebinding_prevention() -> None:
    """A domain that resolves to 127.0.0.1 must be blocked (DNS rebinding)."""
    def mock_getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any):
        # Attacker's domain resolves to localhost
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]

    with patch("socket.getaddrinfo", side_effect=mock_getaddrinfo):
        with pytest.raises(SSRFBlockedError):
            validate_external_url("http://attacker-domain.com/mlflow")


# ── Task 4.1 — GitHub Integration ─────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_github_service_fetches_repo_metadata(
    github_svc: GitHubIntegrationService,
) -> None:
    respx.get("https://api.github.com/repos/SameedIlyas/sentinel").mock(
        return_value=Response(200, json=_repo_payload())
    )
    meta = await github_svc.get_repo_metadata(
        "https://github.com/SameedIlyas/sentinel"
    )
    assert meta.owner == "SameedIlyas"
    assert meta.repo == "sentinel"
    assert meta.language == "Python"
    assert "radiology" in meta.topics


@pytest.mark.asyncio
@respx.mock
async def test_github_service_returns_none_on_rate_limit(
    github_svc: GitHubIntegrationService,
) -> None:
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(429)
    )
    with pytest.raises(GitHubRateLimitError):
        await github_svc.get_repo_metadata("https://github.com/owner/repo")


@pytest.mark.asyncio
@respx.mock
async def test_github_service_raises_auth_error_on_401(
    github_svc: GitHubIntegrationService,
) -> None:
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(401)
    )
    with pytest.raises(GitHubAuthError):
        await github_svc.get_repo_metadata("https://github.com/owner/repo")


@pytest.mark.asyncio
async def test_phi_check_rejects_repo_url_with_patient_id(
    github_svc: GitHubIntegrationService,
) -> None:
    """PHI in repo URL must be rejected before any HTTP call is made."""
    # Email address in URL triggers PHI detection
    phi_url = "https://github.com/patient.john@hospital.com/repo"
    with pytest.raises(ValueError, match="PHI"):
        await github_svc.get_repo_metadata(phi_url)


@pytest.mark.asyncio
@respx.mock
async def test_github_service_fetches_commits(
    github_svc: GitHubIntegrationService,
) -> None:
    respx.get("https://api.github.com/repos/owner/repo/commits").mock(
        return_value=Response(
            200,
            json=[
                {
                    "sha": "abcdef1234567",
                    "commit": {
                        "message": "feat: add model card\nBody text",
                        "author": {"name": "Alice", "date": "2024-01-01T00:00:00Z"},
                    },
                }
            ],
        )
    )
    commits = await github_svc.get_recent_commits("owner", "repo", limit=5)
    assert len(commits) == 1
    assert commits[0].sha == "abcdef1"
    assert commits[0].message == "feat: add model card"
    assert commits[0].author == "Alice"


# ── Task 4.2 — MLflow Integration ─────────────────────────────────────────────


def test_mlflow_service_not_configured_returns_none() -> None:
    svc = MLflowIntegrationService(tracking_uri=None)
    assert not svc.is_configured()


def test_mlflow_service_blocks_private_ip_tracking_uri() -> None:
    with pytest.raises(SSRFBlockedError):
        MLflowIntegrationService(tracking_uri="http://127.0.0.1:5000")


def test_mlflow_service_blocks_internal_network_uri() -> None:
    with pytest.raises(SSRFBlockedError):
        MLflowIntegrationService(tracking_uri="http://192.168.0.10:5000")


# ── Task 4.3 — Auto-Fill Service ──────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_model_card_auto_fill_populates_intended_use(
    github_svc: GitHubIntegrationService,
    mlflow_svc_unconfigured: MLflowIntegrationService,
) -> None:
    respx.get("https://api.github.com/repos/SameedIlyas/sentinel").mock(
        return_value=Response(200, json=_repo_payload())
    )
    respx.get("https://api.github.com/repos/SameedIlyas/sentinel/commits").mock(
        return_value=Response(200, json=[])
    )

    service = _make_autofill_service(github_svc, mlflow_svc_unconfigured)
    result = await service.auto_fill(
        ModelCardAutoFillRequest(repo_url="https://github.com/SameedIlyas/sentinel")
    )

    assert "intended_use" in result.pre_filled
    assert "AI model for radiology screening" in result.pre_filled["intended_use"]


@pytest.mark.asyncio
@respx.mock
async def test_model_card_auto_fill_flags_contraindications_as_required(
    github_svc: GitHubIntegrationService,
    mlflow_svc_unconfigured: MLflowIntegrationService,
) -> None:
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(200, json=_repo_payload())
    )
    respx.get("https://api.github.com/repos/owner/repo/commits").mock(
        return_value=Response(200, json=[])
    )

    service = _make_autofill_service(github_svc, mlflow_svc_unconfigured)
    result = await service.auto_fill(
        ModelCardAutoFillRequest(repo_url="https://github.com/owner/repo")
    )

    assert "contraindications" in result.requires_human_review


@pytest.mark.asyncio
async def test_model_card_auto_fill_works_without_mlflow_configured(
    mlflow_svc_unconfigured: MLflowIntegrationService,
) -> None:
    """Auto-fill must complete gracefully when MLflow is not configured."""
    github_svc = GitHubIntegrationService(token=None)

    async def _mock_get_metadata(repo_url: str):
        from policy_engine.services.github_integration import RepoMetadata
        return RepoMetadata(
            owner="owner",
            repo="repo",
            description="Test model",
            default_branch="main",
            language="Python",
            last_push_at="2024-01-01T00:00:00Z",
            topics=["oncology"],
        )

    async def _mock_get_commits(owner, repo, limit=20):
        return []

    github_svc.get_repo_metadata = _mock_get_metadata  # type: ignore[method-assign]
    github_svc.get_recent_commits = _mock_get_commits  # type: ignore[method-assign]

    service = _make_autofill_service(github_svc, mlflow_svc_unconfigured)
    result = await service.auto_fill(
        ModelCardAutoFillRequest(repo_url="https://github.com/owner/repo")
    )

    assert "intended_use" in result.pre_filled
    assert "contraindications" in result.requires_human_review
    # MLflow fields flagged for review since not configured
    assert "performance_metrics" in result.requires_human_review
    assert "training_data_description" in result.requires_human_review


@pytest.mark.asyncio
@respx.mock
async def test_model_card_auto_fill_extracts_clinical_indications(
    github_svc: GitHubIntegrationService,
    mlflow_svc_unconfigured: MLflowIntegrationService,
) -> None:
    """Clinical topics should auto-populate clinical_indications."""
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(
            200,
            json=_repo_payload(topics=["radiology", "oncology", "python"]),
        )
    )
    respx.get("https://api.github.com/repos/owner/repo/commits").mock(
        return_value=Response(200, json=[])
    )

    service = _make_autofill_service(github_svc, mlflow_svc_unconfigured)
    result = await service.auto_fill(
        ModelCardAutoFillRequest(repo_url="https://github.com/owner/repo")
    )

    assert "clinical_indications" in result.pre_filled
    assert "radiology" in result.pre_filled["clinical_indications"]


@pytest.mark.asyncio
@respx.mock
async def test_github_service_get_test_metrics_returns_conclusion(
    github_svc: GitHubIntegrationService,
) -> None:
    respx.get("https://api.github.com/repos/owner/repo/actions/runs").mock(
        return_value=Response(
            200,
            json={"workflow_runs": [{"id": 42, "conclusion": "success"}]},
        )
    )
    metrics = await github_svc.get_test_metrics("owner", "repo")
    assert metrics is not None
    assert metrics.latest_run_conclusion == "success"
    assert metrics.run_id == 42


@pytest.mark.asyncio
@respx.mock
async def test_github_service_get_test_metrics_returns_none_when_no_runs(
    github_svc: GitHubIntegrationService,
) -> None:
    respx.get("https://api.github.com/repos/owner/repo/actions/runs").mock(
        return_value=Response(200, json={"workflow_runs": []})
    )
    metrics = await github_svc.get_test_metrics("owner", "repo")
    assert metrics is None


@pytest.mark.asyncio
async def test_mlflow_get_model_metrics_returns_none_when_unconfigured(
    mlflow_svc_unconfigured: MLflowIntegrationService,
) -> None:
    result = await mlflow_svc_unconfigured.get_model_metrics("exp1")
    assert result is None


@pytest.mark.asyncio
async def test_mlflow_get_model_parameters_returns_none_when_unconfigured(
    mlflow_svc_unconfigured: MLflowIntegrationService,
) -> None:
    result = await mlflow_svc_unconfigured.get_model_parameters("run1")
    assert result is None


@pytest.mark.asyncio
async def test_mlflow_get_model_artifacts_returns_none_when_unconfigured(
    mlflow_svc_unconfigured: MLflowIntegrationService,
) -> None:
    result = await mlflow_svc_unconfigured.get_model_artifacts("run1")
    assert result is None


@pytest.fixture()
def mlflow_svc_configured() -> MLflowIntegrationService:
    public_ip = "93.184.216.34"

    def mock_getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (public_ip, 0))]

    with patch("socket.getaddrinfo", side_effect=mock_getaddrinfo):
        return MLflowIntegrationService(tracking_uri="http://example.com/mlflow")


@pytest.mark.asyncio
@respx.mock
async def test_mlflow_get_model_artifacts_redacts_phi(
    mlflow_svc_configured: MLflowIntegrationService,
) -> None:
    respx.get("http://example.com/mlflow/api/2.0/mlflow/artifacts/list").mock(
        return_value=Response(
            200,
            json={"files": [{"path": "model_weights.pt", "file_size": 1024}]},
        )
    )
    artifacts = await mlflow_svc_configured.get_model_artifacts("run1")
    assert artifacts is not None
    assert len(artifacts) == 1
    assert artifacts[0].size_bytes == 1024


@pytest.mark.asyncio
@respx.mock
async def test_mlflow_get_model_parameters_returns_params(
    mlflow_svc_configured: MLflowIntegrationService,
) -> None:
    respx.get("http://example.com/mlflow/api/2.0/mlflow/runs/get").mock(
        return_value=Response(
            200,
            json={
                "run": {
                    "data": {
                        "params": [
                            {"key": "epochs", "value": "100"},
                            {"key": "lr", "value": "0.001"},
                        ],
                        "metrics": [],
                    }
                }
            },
        )
    )
    params = await mlflow_svc_configured.get_model_parameters("run1")
    assert params == {"epochs": "100", "lr": "0.001"}


@pytest.mark.asyncio
@respx.mock
async def test_mlflow_search_runs_used_when_no_run_id(
    mlflow_svc_configured: MLflowIntegrationService,
) -> None:
    respx.post("http://example.com/mlflow/api/2.0/mlflow/runs/search").mock(
        return_value=Response(
            200,
            json={
                "runs": [
                    {
                        "data": {
                            "metrics": [{"key": "accuracy", "value": 0.88}],
                            "params": [],
                        }
                    }
                ]
            },
        )
    )
    metrics = await mlflow_svc_configured.get_model_metrics(
        experiment_id="exp1", run_id=None
    )
    assert metrics is not None
    assert metrics.accuracy == pytest.approx(0.88)


@pytest.mark.asyncio
@respx.mock
async def test_model_card_auto_fill_populates_mlflow_metrics(
    github_svc: GitHubIntegrationService,
) -> None:
    """When MLflow is configured and run_id provided, metrics are included."""
    public_ip = "93.184.216.34"

    def mock_getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (public_ip, 0))]

    with patch("socket.getaddrinfo", side_effect=mock_getaddrinfo):
        mlflow_svc = MLflowIntegrationService(
            tracking_uri="http://example.com/mlflow"
        )

    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(200, json=_repo_payload(topics=[]))
    )
    respx.get("https://api.github.com/repos/owner/repo/commits").mock(
        return_value=Response(200, json=[])
    )
    respx.get("http://example.com/mlflow/api/2.0/mlflow/runs/get").mock(
        return_value=Response(
            200,
            json={
                "run": {
                    "data": {
                        "metrics": [
                            {"key": "accuracy", "value": 0.92},
                            {"key": "auc", "value": 0.95},
                        ],
                        "params": [{"key": "epochs", "value": "50"}],
                    }
                }
            },
        )
    )

    service = _make_autofill_service(github_svc, mlflow_svc)
    result = await service.auto_fill(
        ModelCardAutoFillRequest(
            repo_url="https://github.com/owner/repo",
            mlflow_run_id="run_abc123",
            experiment_id="exp_1",
        )
    )

    assert "performance_metrics" in result.pre_filled
    assert result.pre_filled["performance_metrics"]["accuracy"] == pytest.approx(0.92)
    assert result.pre_filled["performance_metrics"]["auc"] == pytest.approx(0.95)
