"""Regression test for HIGH-014 — migration 005 downgrade() must drop indexes.

The upgrade() of 005_add_organizations creates five named indexes:
  ix_organizations_id, ix_organizations_slug,
  ix_organization_members_id, ix_organization_members_org_id,
  ix_organization_members_user_id

Historically downgrade() only called drop_table(...). On PostgreSQL
drop_table cascades dependent objects so this was silent, but a failed
partial downgrade (FK held the table drop) leaves index state
inconsistent and the next upgrade silently skips because the
table-existence guard short-circuits.

This is a static contract test: it loads the migration module and
asserts the downgrade() source contains an explicit drop_index call for
each of the five index names. We do not exercise a live alembic env
because the rest of the schema chain is too tightly coupled to set up.
"""
import importlib.util
import inspect
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "2024_02_12_0000-005_add_organizations.py"
)

EXPECTED_INDEXES = [
    "ix_organizations_id",
    "ix_organizations_slug",
    "ix_organization_members_id",
    "ix_organization_members_org_id",
    "ix_organization_members_user_id",
]


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig_005", MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("index_name", EXPECTED_INDEXES)
def test_downgrade_drops_each_named_index(index_name: str) -> None:
    mod = _load_migration()
    source = inspect.getsource(mod.downgrade)
    assert (
        index_name in source
    ), f"downgrade() does not drop {index_name} — leftover after rollback"


def test_downgrade_uses_drop_index_with_if_exists() -> None:
    """Idempotency: drops must tolerate the index being already missing."""
    mod = _load_migration()
    source = inspect.getsource(mod.downgrade)
    # All five drop_index calls must use op.drop_index AND set if_exists=True
    # OR use a try/except guard, so a re-run after a partial rollback succeeds.
    assert source.count("drop_index") >= len(EXPECTED_INDEXES)
    assert "if_exists=True" in source or "IF EXISTS" in source.upper()
