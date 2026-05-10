"""Independent PHI scan over factory output (review H3 — circular
self-validation prohibited).

``phi_text_check`` is the SUT for clinic routes — using it to validate
its own fixtures would mean any class of PHI the regex misses would also
slip into fixtures undetected. So we run a SECOND, independent scanner
(presidio-analyzer) over every factory output and assert no findings.

When presidio is unavailable (Python < 3.10 or not installed in the
current env), the test skips with a clear marker rather than silently
passing — that keeps the gap visible in CI summaries.
"""

from __future__ import annotations

import sys

import pytest


pytestmark = pytest.mark.clinic


def _presidio_enabled_in_env() -> bool:
    """Gate on an explicit env var rather than dynamic capability detection.

    Importing spaCy / presidio at collection time is itself slow (10s+ in
    sandboxed environments) because spaCy's package init eagerly loads
    other extensions. Using ``PHI_META_SCAN_ENABLED=1`` in CI keeps local
    `pytest` snappy while still surfacing the meta-scan in CI summaries.
    """
    import os
    return os.environ.get("PHI_META_SCAN_ENABLED") == "1"


@pytest.mark.skipif(
    not _presidio_enabled_in_env(),
    reason="set PHI_META_SCAN_ENABLED=1 (CI does this; local dev skips)",
)
def test_factory_strings_pass_independent_phi_scan() -> None:
    """presidio-analyzer over every static factory string — zero findings.

    Confidence floor: 0.5 (presidio's default high-confidence threshold).
    Anything above that is a real PHI signal that ``phi_text_check`` may
    have missed.
    """
    from presidio_analyzer import AnalyzerEngine

    from tests.factories.phi_safe import (
        CLINIC_NAMES,
        CLINIC_SLUGS,
        SAFE_OBSERVATION_HOSTS,
        SAFE_TOOL_FINGERPRINTS,
        SAFE_TOOL_NAMES,
        SAFE_TOOL_NOTES,
        SAFE_TOOL_VENDORS,
    )

    analyzer = AnalyzerEngine()
    free_text = (
        list(CLINIC_NAMES)
        + list(CLINIC_SLUGS)
        + list(SAFE_TOOL_NOTES)
        + list(SAFE_TOOL_NAMES)
        + list(SAFE_TOOL_VENDORS)
        + list(SAFE_OBSERVATION_HOSTS)
        + list(SAFE_TOOL_FINGERPRINTS)
    )
    leaks: list[tuple[str, list]] = []
    for s in free_text:
        results = analyzer.analyze(text=s, language="en")
        high_confidence = [r for r in results if r.score >= 0.5]
        # Presidio flags PERSON, LOCATION, ORG-style entities that are
        # NOT PHI in our context (a fictional clinic name is a brand,
        # not a patient identifier). Filter those out and only fail on
        # PHI-shaped entities.
        phi_entities = {
            "US_SSN",
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "DATE_TIME",
            "MEDICAL_LICENSE",
            "US_DRIVER_LICENSE",
            "US_PASSPORT",
            "IBAN_CODE",
            "CREDIT_CARD",
            "CRYPTO",
            "IP_ADDRESS",
            "US_BANK_NUMBER",
            "US_ITIN",
        }
        phi_hits = [r for r in high_confidence if r.entity_type in phi_entities]
        if phi_hits:
            leaks.append((s, phi_hits))

    assert leaks == [], (
        f"presidio-analyzer flagged PHI in factory fixtures: {leaks}. "
        "Update phi_safe.py to use synthetic strings that satisfy BOTH "
        "phi_text_check and presidio-analyzer."
    )


def test_factory_strings_pass_inhouse_phi_scan() -> None:
    """In-house ``phi_text_check`` scan — every factory string clean.

    This is the cheaper, deterministic gate; presidio above is the
    independent verifier. Both must pass."""
    from policy_engine.services.phi_text_check import scan_for_phi
    from tests.factories.phi_safe import (
        CLINIC_NAMES,
        SAFE_OBSERVATION_HOSTS,
        SAFE_TOOL_FINGERPRINTS,
        SAFE_TOOL_NAMES,
        SAFE_TOOL_NOTES,
        SAFE_TOOL_VENDORS,
    )

    free_text = (
        list(CLINIC_NAMES)
        + list(SAFE_TOOL_NOTES)
        + list(SAFE_TOOL_NAMES)
        + list(SAFE_TOOL_VENDORS)
        + list(SAFE_OBSERVATION_HOSTS)
        + list(SAFE_TOOL_FINGERPRINTS)
    )
    findings = [(s, scan_for_phi("test", s)) for s in free_text]
    leaks = [(s, f) for s, f in findings if f is not None]
    assert leaks == [], f"phi_text_check flagged factory strings: {leaks}"
