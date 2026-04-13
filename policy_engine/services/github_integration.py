"""GitHub Integration Service for CHAI model card auto-fill."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
from policy_engine.services.url_validator import validate_github_url

logger = logging.getLogger(__name__)


class GitHubAuthError(Exception):
    """Raised when GitHub returns 401 Unauthorized."""


class GitHubRateLimitError(Exception):
    """Raised when GitHub returns 429 Too Many Requests."""


@dataclass
class RepoMetadata:
    owner: str
    repo: str
    description: Optional[str]
    default_branch: str
    language: Optional[str]
    last_push_at: str
    topics: List[str] = field(default_factory=list)


@dataclass
class CommitSummary:
    sha: str        # first 7 chars
    message: str    # first line only
    author: str
    date: str       # ISO8601


@dataclass
class TestMetrics:
    latest_run_conclusion: Optional[str]  # "success", "failure", None
    run_id: Optional[int]


def _build_headers(token: Optional[str]) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise GitHubAuthError("GitHub authentication failed")
    if response.status_code == 429:
        raise GitHubRateLimitError("GitHub rate limit exceeded")
    if response.status_code == 404:
        raise ValueError("Repository not found")
    if not response.is_success:
        raise ValueError(f"GitHub API error: {response.status_code}")


class GitHubIntegrationService:
    """Fetches repository metadata for CHAI model card auto-fill."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://api.github.com",
        timeout_seconds: int = 10,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(
            connect=5.0, read=float(timeout_seconds), write=5.0, pool=5.0
        )
        self._phi_engine = PHIRedactionEngine()

    async def get_repo_metadata(self, repo_url: str) -> RepoMetadata:
        """Fetch repo description, language, topics, and push date."""
        # Check PHI on the path portion only — the full URL always triggers the
        # broad URL regex in PHI_PATTERNS (https?://[^\s]+), giving false positives.
        # We want to catch PHI *embedded* in the path (e.g. patient emails as owner).
        _PREFIX = "https://github.com/"
        path_to_check = (
            repo_url[len(_PREFIX):] if repo_url.startswith(_PREFIX) else repo_url
        )
        if self._phi_engine.contains_phi(path_to_check):
            raise ValueError("PHI detected in repository URL")
        owner, repo = validate_github_url(repo_url)
        url = f"{self._base_url}/repos/{owner}/{repo}"
        async with httpx.AsyncClient(
            headers=_build_headers(self._token), timeout=self._timeout
        ) as client:
            response = await client.get(url)
        _raise_for_status(response)
        data = response.json()
        return RepoMetadata(
            owner=owner,
            repo=repo,
            description=data.get("description"),
            default_branch=data.get("default_branch", "main"),
            language=data.get("language"),
            last_push_at=data.get("pushed_at", ""),
            topics=data.get("topics", []),
        )

    async def get_recent_commits(
        self, owner: str, repo: str, limit: int = 20
    ) -> List[CommitSummary]:
        """Fetch last N commits (sha[:7], first message line, author, date)."""
        url = f"{self._base_url}/repos/{owner}/{repo}/commits"
        async with httpx.AsyncClient(
            headers=_build_headers(self._token), timeout=self._timeout
        ) as client:
            response = await client.get(url, params={"per_page": limit})
        _raise_for_status(response)
        results: List[CommitSummary] = []
        for item in response.json():
            commit_data = item.get("commit", {})
            author_data = commit_data.get("author", {})
            message = commit_data.get("message", "")
            results.append(
                CommitSummary(
                    sha=item.get("sha", "")[:7],
                    message=message.split("\n")[0],
                    author=author_data.get("name", "unknown"),
                    date=author_data.get("date", ""),
                )
            )
        return results

    async def get_test_metrics(
        self, owner: str, repo: str
    ) -> Optional[TestMetrics]:
        """Fetch latest CI/CD run conclusion. Returns None if no runs exist."""
        url = f"{self._base_url}/repos/{owner}/{repo}/actions/runs"
        async with httpx.AsyncClient(
            headers=_build_headers(self._token), timeout=self._timeout
        ) as client:
            response = await client.get(url, params={"per_page": 1})
        if response.status_code == 404:
            return None
        _raise_for_status(response)
        runs = response.json().get("workflow_runs", [])
        if not runs:
            return None
        latest = runs[0]
        return TestMetrics(
            latest_run_conclusion=latest.get("conclusion"),
            run_id=latest.get("id"),
        )
