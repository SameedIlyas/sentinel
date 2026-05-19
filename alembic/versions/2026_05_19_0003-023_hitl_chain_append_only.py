"""Make ``hitl_audit_trail`` append-only and recompute legacy hashes.

CRIT-002 + CRIT-003 (PR #12) — make the HITL audit chain
machine-verifiable and tamper-evident:

1. ``entry_hash`` becomes ``NOT NULL`` and loses its empty-string
   default (every legitimate append now computes a real hash).
2. Postgres only: a BEFORE UPDATE trigger refuses any UPDATE that
   changes the hash-binding columns (``entry_hash``, ``comments``,
   ``action``, ``old_status``, ``new_status``, ``actor_id``,
   ``timestamp``). SQLite has no triggers but the application path no
   longer issues UPDATEs against these columns — tests document the
   gap.
3. Backfill: under the new domain logic the entry hash is
   recomputed from the previous *persisted* hash and the normalised
   timestamp shape. We rebuild every chain once so existing rows
   verify True under the post-PR-#12 verifier.

Revision ID: 023
Revises: 022
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


_TRIGGER_FN_NAME = "hitl_audit_trail_no_update"
_TRIGGER_NAME = "hitl_audit_trail_before_update"


def _normalise_timestamp(ts) -> str:
    """Mirror policy_engine.domain.clinical.hitl._normalise_timestamp.

    Inlined here so the migration is independent of application imports
    at upgrade time.
    """
    if isinstance(ts, datetime):
        if ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        return ts.isoformat()
    if isinstance(ts, str):
        s = ts
        if s.endswith("Z"):
            s = s[:-1]
        if s.endswith("+00:00"):
            s = s[:-6]
        return s
    return str(ts)


def _hash_entry(row: dict, prev_hash: str) -> str:
    content = json.dumps(
        {
            "prev_hash": prev_hash,
            "actor_id": row.get("actor_id") or "",
            "action": row.get("action"),
            "old_status": row.get("old_status"),
            "new_status": row.get("new_status"),
            "comments": row.get("comments"),
            "timestamp": _normalise_timestamp(row.get("timestamp")),
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "hitl_audit_trail" not in set(inspector.get_table_names()):
        return

    # ── 1. Backfill: recompute every chain under the new shape ─────────
    rows = bind.execute(
        sa.text(
            "SELECT id, review_id, actor_id, action, old_status, "
            "new_status, comments, timestamp FROM hitl_audit_trail "
            "ORDER BY review_id, timestamp, id"
        )
    ).fetchall()
    prev_hashes: dict[str, str] = {}
    for row in rows:
        row_dict = {
            "actor_id": row[2],
            "action": row[3],
            "old_status": row[4],
            "new_status": row[5],
            "comments": row[6],
            "timestamp": row[7],
        }
        review_id = row[1]
        prev = prev_hashes.get(review_id, "")
        h = _hash_entry(row_dict, prev)
        bind.execute(
            sa.text(
                "UPDATE hitl_audit_trail SET entry_hash = :h WHERE id = :id"
            ),
            {"h": h, "id": row[0]},
        )
        prev_hashes[review_id] = h

    # ── 2. NOT NULL + drop default ─────────────────────────────────────
    cols = {c["name"]: c for c in inspector.get_columns("hitl_audit_trail")}
    if "entry_hash" in cols:
        with op.batch_alter_table("hitl_audit_trail") as batch:
            batch.alter_column(
                "entry_hash",
                existing_type=sa.String(),
                nullable=False,
                server_default=None,
            )

    # ── 3. Postgres-only BEFORE UPDATE trigger ─────────────────────────
    if bind.dialect.name == "postgresql":
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {_TRIGGER_FN_NAME}()
            RETURNS trigger AS $$
            BEGIN
                IF NEW.entry_hash    IS DISTINCT FROM OLD.entry_hash
                OR NEW.comments      IS DISTINCT FROM OLD.comments
                OR NEW.action        IS DISTINCT FROM OLD.action
                OR NEW.old_status    IS DISTINCT FROM OLD.old_status
                OR NEW.new_status    IS DISTINCT FROM OLD.new_status
                OR NEW.actor_id      IS DISTINCT FROM OLD.actor_id
                OR NEW."timestamp"   IS DISTINCT FROM OLD."timestamp"
                THEN
                    RAISE EXCEPTION
                        'hitl_audit_trail is append-only (CRIT-002)';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"""
            DROP TRIGGER IF EXISTS {_TRIGGER_NAME} ON hitl_audit_trail;
            CREATE TRIGGER {_TRIGGER_NAME}
                BEFORE UPDATE ON hitl_audit_trail
                FOR EACH ROW EXECUTE FUNCTION {_TRIGGER_FN_NAME}();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "hitl_audit_trail" not in set(inspector.get_table_names()):
        return

    if bind.dialect.name == "postgresql":
        op.execute(
            f"DROP TRIGGER IF EXISTS {_TRIGGER_NAME} ON hitl_audit_trail;"
        )
        op.execute(f"DROP FUNCTION IF EXISTS {_TRIGGER_FN_NAME}();")

    cols = {c["name"]: c for c in inspector.get_columns("hitl_audit_trail")}
    if "entry_hash" in cols and cols["entry_hash"].get("nullable") is False:
        with op.batch_alter_table("hitl_audit_trail") as batch:
            batch.alter_column(
                "entry_hash",
                existing_type=sa.String(),
                nullable=True,
                server_default="",
            )
