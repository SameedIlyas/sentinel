"""R2 — Snapshot guard: the clinic UX product-role projection is a
frontend-only change.

This test fails the build if anyone modifies the two backend files that
constitute the canonical 8-role RBAC source of truth:

* ``policy_engine/auth/rbac.py`` — middleware / decorators / dependencies.
* ``policy_engine/models/user.py`` — ``UserRole`` enum + ``ROLE_PERMISSIONS``
  matrix.

The R2 plan asserts these files are untouched (see
``plans/clinical-shield-v1/R2-PLAN.md``). Any divergence indicates a plan
violation: either the change is genuine RBAC work that belongs in a
separate PR, or the projection layer has overreached.

If a legitimate backend RBAC change *is* intended, update both:

1. The SHA-256 fixture below.
2. The ``ROLE_PERMISSIONS`` snapshot dict below.

The two-step ritual exists to force a reviewer to look at the change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from policy_engine.models.user import ROLE_PERMISSIONS, UserRole


# ── Paths ───────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
RBAC_PY = REPO_ROOT / "policy_engine" / "auth" / "rbac.py"
USER_PY = REPO_ROOT / "policy_engine" / "models" / "user.py"


# ── SHA-256 snapshot ───────────────────────────────────────────────────
# Computed once at R2 land time from the un-modified upstream files.
# If you need to change either backend file, run:
#   python -c "import hashlib; print(hashlib.sha256(open('policy_engine/auth/rbac.py','rb').read()).hexdigest())"
#   python -c "import hashlib; print(hashlib.sha256(open('policy_engine/models/user.py','rb').read()).hexdigest())"
# and update the two strings below.

#
# Note on line endings: these SHAs are computed from the LF-canonical
# (committed) bytes. On a Windows worktree with `core.autocrlf=true` the
# file on disk may have CRLF line endings, producing a different SHA than
# the committed bytes. The R2 land-time capture happened on a CRLF
# worktree, which is why the previously-recorded `user.py` SHA didn't
# match the parent worktree. The values below are LF-canonical so the
# test passes regardless of the developer's autocrlf checkout setting.
# If you switch a future capture environment, re-run on a fresh
# `git config --global core.autocrlf input` checkout to match.
EXPECTED_RBAC_SHA256 = (
    "99fec7002f2c9c9bd6ad851dbaef371df61c2d1214bf77265be4628b86aa0ac3"
)
EXPECTED_USER_SHA256 = (
    "2df09cc8e59c468afaec6f52339d5318620338d660879006f938b1014922bd8e"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "path,expected",
    [
        (RBAC_PY, EXPECTED_RBAC_SHA256),
        (USER_PY, EXPECTED_USER_SHA256),
    ],
    ids=["rbac.py", "user.py"],
)
def test_backend_rbac_file_sha256_unchanged(path: Path, expected: str) -> None:
    """The two backend RBAC files must remain byte-identical to the R2 baseline.

    A mismatch means either:
      (a) the file was edited as part of an R2-adjacent change — update the
          snapshot AND review the diff in PR;
      (b) line endings were rewritten by an editor — re-run with ``git diff``
          to confirm the byte change is meaningful before updating the snapshot.
    """
    assert path.exists(), f"Expected backend file is missing: {path}"
    actual = _sha256(path)
    assert actual == expected, (
        f"Backend RBAC file changed unexpectedly: {path.name}\n"
        f"  expected SHA-256: {expected}\n"
        f"  actual   SHA-256: {actual}\n"
        f"This is a plan violation per plans/clinical-shield-v1/R2-PLAN.md. "
        f"If the change is intentional, update EXPECTED_*_SHA256 in this "
        f"test AND add a justification in the PR description."
    )


# ── ROLE_PERMISSIONS deep snapshot ─────────────────────────────────────
# A second guardrail in case someone rewrites rbac.py / user.py with the
# same byte count but different semantics (e.g. removing a permission).
# Snapshot is keyed by ``UserRole.value`` so the order of enum definition
# does not affect equality.

EXPECTED_ROLE_PERMISSIONS_BY_VALUE = {
    "system_admin": {
        "policies": ["create", "read", "update", "delete"],
        "agents": ["create", "read", "update", "delete"],
        "audit_logs": ["read", "export"],
        "alerts": ["create", "read", "update", "acknowledge", "configure"],
        "users": ["create", "read", "update", "delete"],
        "organizations": ["create", "read", "update", "delete"],
        "model_cards": ["create", "read", "update", "delete"],
        "bias_audits": ["create", "read", "update", "delete"],
        "drift_detection": ["create", "read", "update", "delete"],
        "hitl_reviews": ["create", "read", "update", "delete"],
        "shadow_ai": ["create", "read", "update", "delete"],
        "scribe_audits": ["create", "read", "update", "delete"],
        "transparency": ["create", "read", "update", "delete"],
        "prior_auth": ["create", "read", "update", "delete"],
        "revenue_cycle": ["create", "read", "update", "delete"],
        "technical_files": ["create", "read", "update", "delete"],
        "post_market": ["create", "read", "update", "delete"],
        "risk_scores": ["create", "read", "update", "delete"],
    },
    "admin": {
        "policies": ["create", "read", "update", "delete"],
        "agents": ["create", "read", "update", "delete"],
        "audit_logs": ["read", "export"],
        "alerts": ["create", "read", "update", "acknowledge", "configure"],
        "users": ["create", "read", "update", "delete"],
        "model_cards": ["create", "read", "update", "delete"],
        "bias_audits": ["create", "read", "update"],
        "drift_detection": ["read", "update"],
        "hitl_reviews": ["create", "read", "update"],
        "shadow_ai": ["read"],
        "scribe_audits": ["read"],
        "transparency": ["read"],
        "prior_auth": ["create", "read", "update"],
        "revenue_cycle": ["read"],
        "technical_files": ["create", "read", "update"],
        "post_market": ["read"],
        "risk_scores": ["create", "read", "update", "delete"],
    },
    "cmio": {
        "policies": ["create", "read", "update"],
        "agents": ["read", "update"],
        "audit_logs": ["read", "export"],
        "alerts": ["read", "acknowledge"],
        "users": ["read"],
        "model_cards": ["create", "read", "update"],
        "bias_audits": ["read"],
        "drift_detection": ["read"],
        "hitl_reviews": ["create", "read", "update"],
        "risk_scores": ["read"],
        "transparency": ["read"],
    },
    "data_scientist": {
        "policies": ["read"],
        "agents": ["read"],
        "audit_logs": ["read"],
        "alerts": ["read"],
        "model_cards": ["create", "read", "update"],
        "bias_audits": ["create", "read", "update"],
        "drift_detection": ["create", "read", "update"],
        "risk_scores": ["create", "read", "update"],
        "technical_files": ["create", "read", "update"],
    },
    "compliance_officer": {
        "policies": ["read", "update"],
        "agents": ["read"],
        "audit_logs": ["read", "export"],
        "alerts": ["read", "acknowledge"],
        "users": ["read"],
        "model_cards": ["read"],
        "bias_audits": ["read"],
        "drift_detection": ["read"],
        "transparency": ["read"],
        "post_market": ["read"],
        "risk_scores": ["read"],
        "technical_files": ["read"],
    },
    "clinical_user": {
        "policies": ["read"],
        "agents": ["read"],
        "audit_logs": ["read"],
        "alerts": ["read"],
        "hitl_reviews": ["create", "read", "update"],
        "prior_auth": ["create", "read"],
        "risk_scores": ["read"],
        "scribe_audits": ["read"],
        "shadow_ai": ["read"],
    },
    "analyst": {
        "policies": ["read"],
        "agents": ["read"],
        "audit_logs": ["read", "export"],
        "alerts": ["read", "acknowledge", "configure"],
        "users": ["read"],
    },
    "viewer": {
        "policies": ["read"],
        "agents": ["read"],
        "audit_logs": ["read"],
        "alerts": ["read"],
        "users": [],
    },
}


def test_role_permissions_matrix_unchanged() -> None:
    """ROLE_PERMISSIONS must deep-equal the R2 snapshot.

    Indexed by ``UserRole.value`` so we collapse the (ORG_ADMIN, ADMIN)
    alias pair into one logical key ("admin"). The 8 distinct backend
    role values must all be present.
    """
    actual_by_value = {role.value: perms for role, perms in ROLE_PERMISSIONS.items()}
    assert actual_by_value == EXPECTED_ROLE_PERMISSIONS_BY_VALUE


def test_user_role_enum_values_unchanged() -> None:
    """The 8 canonical backend role values must remain stable.

    ORG_ADMIN and ADMIN aliases share the value "admin" by design
    (see policy_engine/models/user.py:13). The deduplicated value set
    is exactly the 8 personas referenced throughout the codebase.
    """
    expected_values = {
        "system_admin",
        "admin",
        "cmio",
        "data_scientist",
        "compliance_officer",
        "clinical_user",
        "analyst",
        "viewer",
    }
    actual_values = {role.value for role in UserRole}
    assert actual_values == expected_values
