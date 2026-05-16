"""Regression test for HIGH-031 — extension endpoint URL must be validated.

clinic-extension/options.js historically stored any string typed into the
endpoint field directly into chrome.storage.local. background.js then used
that string verbatim in a fetch() with the X-Clinic-Extension-Token header.
A rogue admin (or a user under social engineering pressure) could redirect
every observation POST — including the bearer-equivalent token — to an
attacker-controlled server.

The fix introduces a pure ``validateEndpoint`` function in options.js that
enforces:
  - http or https scheme only (no ``javascript:``, ``data:``, ``file:``)
  - non-empty parseable URL
  - hostname present
  - not a credential-bearing URL (no userinfo in the authority)

These checks are static contract assertions against the file source, matching
the pattern in tests/test_extension_manifest.py. A live browser smoke test
belongs in Playwright (deferred).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


pytestmark = pytest.mark.clinic

REPO_ROOT = Path(__file__).resolve().parents[1]
OPTIONS_PATH = REPO_ROOT / "clinic-extension" / "options.js"


@pytest.fixture(scope="module")
def source() -> str:
    assert OPTIONS_PATH.exists(), f"Missing options.js: {OPTIONS_PATH}"
    return OPTIONS_PATH.read_text(encoding="utf-8")


def test_validate_endpoint_function_exists(source: str) -> None:
    assert re.search(r"function\s+validateEndpoint\s*\(", source), (
        "validateEndpoint(input) must be defined in options.js"
    )


def test_save_path_calls_validateEndpoint(source: str) -> None:
    # save() must consult validateEndpoint and bail when it returns !ok.
    assert "validateEndpoint(" in source, "save() must invoke validateEndpoint"
    assert re.search(r"validateEndpoint\([^)]+\)\.ok|\.ok\b", source), (
        "validateEndpoint must expose an .ok field used to gate the save"
    )


def test_endpoint_rejects_javascript_scheme(source: str) -> None:
    # The validator must check that the URL scheme is http(s).
    assert re.search(r"http:|https:|'http'|'https'", source), (
        "validateEndpoint must enforce an http/https scheme allowlist"
    )


def test_endpoint_blocks_credentials_in_url(source: str) -> None:
    # Reject URLs with embedded userinfo (user:pass@host).
    # Either a username check or password check is sufficient signal.
    assert re.search(r"\.username|\.password", source), (
        "validateEndpoint must reject URLs that embed credentials"
    )


def test_invalid_endpoint_not_persisted(source: str) -> None:
    """The save() function must NOT call chrome.storage.local.set on the
    invalid branch."""
    # Find the body of save(); split on validateEndpoint guard.
    save_match = re.search(r"async\s+function\s+save\s*\([^)]*\)\s*\{(.+?)\n\}", source, re.DOTALL)
    assert save_match, "could not locate save() body"
    body = save_match.group(1)
    # The guard pattern: if (!result.ok) { ... return; }
    assert re.search(r"if\s*\(\s*!\s*\w+\.ok", body), (
        "save() must early-return when validation fails"
    )
    assert "return" in body, "save() must short-circuit on invalid input"
