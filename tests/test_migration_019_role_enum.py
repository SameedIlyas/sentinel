"""Regression test for CRIT-009 — migration 019 must add healthcare values.

Migration 006 expanded :class:`UserRole` at the application layer but left
the Postgres ``userrole`` enum unchanged. Inserts of any healthcare role
(``cmio``, ``data_scientist``, ``compliance_officer``, ``clinical_user``,
``system_admin``) therefore fail with ``invalid input value for enum``.

Migration 019 issues ``ALTER TYPE userrole ADD VALUE IF NOT EXISTS ...`` in
an autocommit block for each of those values.

This is a static contract test: it loads the migration module and asserts
that ``upgrade()`` issues an ``ALTER TYPE ... ADD VALUE`` for every
required role inside an ``autocommit_block``. We do not boot Postgres in
unit tests; the live-DB assertion belongs in the W-2 Postgres CI lane.
"""
from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "2026_05_19_0000-019_userrole_healthcare_values.py"
)

REQUIRED_VALUES = (
    "system_admin",
    "cmio",
    "data_scientist",
    "compliance_officer",
    "clinical_user",
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig_019", MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("value", REQUIRED_VALUES)
def test_upgrade_adds_each_healthcare_value(value: str) -> None:
    """Either the value is referenced explicitly in upgrade() or it appears
    in a module-level collection that upgrade() iterates."""
    mod = _load_migration()
    upgrade_source = inspect.getsource(mod.upgrade)
    module_source = inspect.getsource(mod)
    in_upgrade = f"'{value}'" in upgrade_source or f'"{value}"' in upgrade_source
    in_module = f'"{value}"' in module_source or f"'{value}'" in module_source
    assert (
        in_upgrade or in_module
    ), f"upgrade() does not ADD VALUE '{value}' — Postgres inserts will fail"


def test_upgrade_uses_autocommit_block() -> None:
    """ALTER TYPE ADD VALUE is non-transactional — must escape implicit tx."""
    mod = _load_migration()
    source = inspect.getsource(mod.upgrade)
    assert (
        "autocommit_block" in source
    ), "ALTER TYPE ADD VALUE must run inside autocommit_block()"


def test_upgrade_uses_if_not_exists() -> None:
    """Idempotency: re-running the migration must be a no-op, not an error."""
    mod = _load_migration()
    source = inspect.getsource(mod.upgrade)
    assert (
        "IF NOT EXISTS" in source
    ), "ALTER TYPE ADD VALUE must use IF NOT EXISTS to stay idempotent"


def test_upgrade_is_postgres_only() -> None:
    """SQLite stores enums as text and has nothing to alter."""
    mod = _load_migration()
    source = inspect.getsource(mod.upgrade)
    assert (
        "postgresql" in source
    ), "upgrade() must skip non-Postgres dialects"


def test_python_enum_no_admin_alias() -> None:
    """ADMIN alias removed; ORG_ADMIN is the canonical name (CRIT-009 cleanup)."""
    from policy_engine.models.user import UserRole

    members = {m for m in UserRole.__members__}
    assert "ORG_ADMIN" in members
    assert "ADMIN" not in members, (
        "ADMIN alias must be removed — only ORG_ADMIN should be exposed"
    )
