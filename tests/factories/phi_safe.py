"""HIPAA Safe-Harbor synthetic strings for fixtures.

Every constant here MUST pass ``phi_text_check.scan_for_phi`` with no
finding. The ``meta_test_phi_safety`` test in Phase 7 verifies this on
every CI run.

Avoid:
- Numbers that look like SSN, MRN, account, phone, or DOB
- Real-looking emails (use ``@example.test`` domain)
- Street addresses (use city/state only)
- Anything that even *resembles* a 9+ digit run

Prefer:
- Place names from PHI-safe synthetic-data lists (small fictional towns)
- Brand names that are obviously fake (``Acme``, ``Foo``, ``QA``)
- Adjective+noun combos
"""

from __future__ import annotations

# Fictional clinic identities — chosen to avoid coincidental matches with
# real practices. Cities are small US municipalities or fictional names.
CLINIC_NAMES: tuple[str, ...] = (
    "Cedar Bluff Family Practice",
    "Northwind Pediatric Group",
    "Acme Allergy Clinic",
    "Foo Valley Internal Medicine",
    "QA Lakeshore Dermatology",
)

CLINIC_SLUGS: tuple[str, ...] = (
    "cedar-bluff",
    "northwind-peds",
    "acme-allergy",
    "foo-valley-im",
    "qa-lakeshore-derm",
)

# Email domain reserved for fixtures only — ``.test`` is RFC 6761 reserved.
EMAIL_DOMAIN = "example.test"

# Tool descriptions intentionally avoid clinical detail. They describe the
# *category* of tool, not any patient-specific use.
SAFE_TOOL_NOTES: tuple[str, ...] = (
    "Used for general note formatting only.",
    "Reviewed by the practice manager monthly.",
    "Vendor offers a click-through BAA on signup.",
    "Configured to run only on workstation A.",
    "Marked low-risk after intake review.",
)

SAFE_TOOL_NAMES: tuple[str, ...] = (
    "Acme Scribe",
    "Foo Documentation Helper",
    "QA Decision Support",
    "Northwind Imaging Assistant",
    "Cedar Communicator",
)

SAFE_TOOL_VENDORS: tuple[str, ...] = (
    "Acme AI",
    "Foo Health Tech",
    "QA Systems",
    "Northwind Software",
)

# Browser-extension fingerprints — these are tool category strings, not
# URLs and not PHI. Hashed page URLs (SHA-256) live in
# ``ClinicAiObservation.page_url_hash`` and are unrelated to these.
SAFE_OBSERVATION_HOSTS: tuple[str, ...] = (
    "chat.acme-ai.test",
    "claude.foo-health.test",
    "scribe.qa-systems.test",
)

SAFE_TOOL_FINGERPRINTS: tuple[str, ...] = (
    "acme_scribe",
    "foo_doc_helper",
    "qa_decision_support",
)


def safe_email(local: str = "admin") -> str:
    """Build a fixture email that no PHI pattern can match."""
    # Local part contains no digits to avoid coincidental MRN-shaped matches.
    return f"{local}@{EMAIL_DOMAIN}"


def safe_legal_name(brand: str = "Acme") -> str:
    """A fictional clinic legal name suitable for BAA acceptance."""
    return f"{brand} Health LLC"


__all__ = [
    "CLINIC_NAMES",
    "CLINIC_SLUGS",
    "EMAIL_DOMAIN",
    "SAFE_TOOL_NOTES",
    "SAFE_TOOL_NAMES",
    "SAFE_TOOL_VENDORS",
    "SAFE_OBSERVATION_HOSTS",
    "SAFE_TOOL_FINGERPRINTS",
    "safe_email",
    "safe_legal_name",
]
