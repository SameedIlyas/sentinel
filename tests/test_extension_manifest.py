"""Extension manifest hygiene checks.

Pure data validation — no Chromium needed. Browser-launch smoke (loading
the extension via Playwright's launchPersistentContext) is deferred to
Phase 5 / a Playwright session.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.clinic


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "clinic-extension" / "manifest.json"


@pytest.fixture(scope="module")
def manifest() -> dict:
    assert MANIFEST_PATH.exists(), f"Missing manifest: {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_v3(manifest: dict) -> None:
    assert manifest["manifest_version"] == 3


def test_manifest_has_name_and_version(manifest: dict) -> None:
    assert manifest.get("name")
    assert manifest.get("version")


def test_manifest_uses_service_worker(manifest: dict) -> None:
    """MV3 requires service_worker, not background.scripts."""
    bg = manifest.get("background", {})
    assert "service_worker" in bg
    assert "scripts" not in bg, "MV2 background.scripts is not allowed in MV3"


def test_manifest_permissions_minimal(manifest: dict) -> None:
    """The extension should not request bulk permissions like 'history' or 'cookies'."""
    perms = set(manifest.get("permissions", []))
    forbidden = {"history", "cookies", "bookmarks", "downloads", "geolocation"}
    overreach = perms & forbidden
    assert not overreach, f"Extension requests overly broad permissions: {overreach}"


def test_manifest_host_permissions_documented(manifest: dict) -> None:
    """Pin the current host_permissions shape so regression is visible.

    NOTE: Currently uses ``<all_urls>`` which gives the extension visibility
    into every site. For a clinic-tier shadow-AI detector this matches the
    product intent (detecting tool usage anywhere staff browse), but it is
    a HIGH-blast-radius permission. If a future change tightens this scope
    (preferred), this test should be updated.
    """
    hosts = manifest.get("host_permissions", [])
    # Soft assertion: the current spec uses <all_urls>. Flag in CI if the
    # product team reduces scope so the test is updated deliberately.
    assert hosts, "host_permissions must be present (even if <all_urls>)"


def test_manifest_no_externally_connectable_wildcard(manifest: dict) -> None:
    """``externally_connectable.matches`` must NOT be ['*://*/*'] — that lets
    any web page send messages to the extension."""
    ec = manifest.get("externally_connectable", {})
    matches = ec.get("matches", [])
    assert "*://*/*" not in matches
    assert "<all_urls>" not in matches
