"""Migration 018 round-trip test (PRD.v2.md §6.8.2.a).

Validates:
* upgrade adds the five new columns
* pre-existing rows are backfilled to 'unknown' / 'not_applicable'
* downgrade cleanly drops the columns
* second upgrade re-adds them (idempotent path on subsequent boots)
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "alembic"
    / "versions"
    / "2026_05_17_0000-018_clinic_model_training_status.py"
)

NEW_COLUMNS = (
    "model_training_status",
    "practice_opt_out_state",
    "opt_out_verified_at",
    "opt_out_verified_by_user_id",
    "model_training_status_evidence",
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig_018", MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_engine() -> sa.Engine:
    """Engine with a minimal clinic_ai_tools + users skeleton."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    md = sa.MetaData()
    sa.Table(
        "users",
        md,
        sa.Column("id", sa.String(), primary_key=True),
    )
    sa.Table(
        "clinic_ai_tools",
        md,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
    )
    md.create_all(eng)
    return eng


def _column_names(eng: sa.Engine, table: str) -> set[str]:
    insp = sa.inspect(eng)
    return {c["name"] for c in insp.get_columns(table)}


@pytest.fixture()
def engine():
    eng = _make_engine()
    try:
        yield eng
    finally:
        eng.dispose()


def test_revision_metadata() -> None:
    mod = _load_migration()
    assert mod.revision == "018"
    assert mod.down_revision == "017"


def test_upgrade_adds_five_columns(engine) -> None:
    mod = _load_migration()
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    # Seed a pre-existing row to exercise the backfill UPDATE.
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO clinic_ai_tools (id, name) VALUES (:i, :n)"),
            {"i": "tool_legacy", "n": "Legacy Tool"},
        )

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        # Replace the alembic.op global on the module so its uses of `op.`
        # bind to our connection-scoped Operations instance.
        mod.op = op
        mod.upgrade()

    cols = _column_names(engine, "clinic_ai_tools")
    for c in NEW_COLUMNS:
        assert c in cols, f"upgrade did not add column {c!r}"

    # Backfill assertion — the legacy row must be non-NULL with defaults.
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT model_training_status, practice_opt_out_state "
                "FROM clinic_ai_tools WHERE id='tool_legacy'"
            )
        ).first()
    assert row is not None
    assert row[0] == "unknown"
    assert row[1] == "not_applicable"


def test_downgrade_drops_added_columns(engine) -> None:
    mod = _load_migration()
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        mod.op = op
        mod.upgrade()
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        mod.op = op
        mod.downgrade()

    cols = _column_names(engine, "clinic_ai_tools")
    for c in NEW_COLUMNS:
        assert c not in cols, f"downgrade did not drop column {c!r}"


def test_round_trip_upgrade_downgrade_upgrade(engine) -> None:
    """upgrade → downgrade → upgrade must leave the schema with the new
    columns and no errors. Mirrors the verification command in the plan."""
    mod = _load_migration()
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    for op_name in ("upgrade", "downgrade", "upgrade"):
        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            op = Operations(ctx)
            mod.op = op
            getattr(mod, op_name)()

    cols = _column_names(engine, "clinic_ai_tools")
    for c in NEW_COLUMNS:
        assert c in cols


def test_downgrade_uses_batch_alter_table() -> None:
    """SQLite-safe ALTER TABLE pattern — matches migration 016 idiom
    (see ``alembic/versions/2024_02_23_0000-016_clinic_tier.py:51``)."""
    mod = _load_migration()
    upgrade_src = inspect.getsource(mod.upgrade)
    downgrade_src = inspect.getsource(mod.downgrade)
    assert "batch_alter_table" in upgrade_src
    assert "batch_alter_table" in downgrade_src
