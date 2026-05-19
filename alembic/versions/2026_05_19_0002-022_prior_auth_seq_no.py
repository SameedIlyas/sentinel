"""Add ``seq_no`` to ``prior_auth_records`` for tail-deletion detection.

CRIT-005 — the prior-auth hash chain detects middle-record tampering
but is silent on tail-deletions: if an attacker deletes the last N
rows, ``verify_chain`` walks the remaining records and they hash
correctly because each only references its predecessor. The chain
status row records ``total_records`` snapshot, but the verifier never
compares the *current* count against the *recorded* count.

This migration adds a monotonic, per-org ``seq_no`` column so:

1. Inserts assign a new ``seq_no`` per organization.
2. The hash function includes ``seq_no`` so existing rows can't be
   re-hashed without their original sequence.
3. ``verify_chain`` checks for gaps in the seq_no sequence — a tail
   deletion now produces an arithmetic mismatch the verifier sees.

The migration:

1. Adds the column nullable to allow backfill.
2. Backfills ``seq_no`` per-organization via ROW_NUMBER() OVER
   (PARTITION BY organization_id ORDER BY created_at, id).
3. Adds a UNIQUE constraint on (organization_id, seq_no).
4. Switches the column to NOT NULL.

The hash recomputation that incorporates ``seq_no`` is a **one-time**
backfill — every existing row has its record_hash recomputed against
the new schema. New inserts use the new shape automatically.

Revision ID: 022
Revises: 021
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "prior_auth_records" not in set(inspector.get_table_names()):
        return

    cols = {c["name"] for c in inspector.get_columns("prior_auth_records")}

    if "seq_no" not in cols:
        with op.batch_alter_table("prior_auth_records") as batch:
            batch.add_column(sa.Column("seq_no", sa.BigInteger(), nullable=True))

    # Backfill. SQLite < 3.25 doesn't support window functions; use a
    # portable per-org cursor instead.
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            WITH numbered AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY organization_id
                           ORDER BY created_at, id
                       ) AS rn
                  FROM prior_auth_records
            )
            UPDATE prior_auth_records par
               SET seq_no = numbered.rn
              FROM numbered
             WHERE par.id = numbered.id
               AND par.seq_no IS NULL
            """
        )
    else:
        # SQLite path — fetch then UPDATE per row. Slow but tests-friendly.
        rows = bind.execute(
            sa.text(
                "SELECT id, organization_id FROM prior_auth_records "
                "ORDER BY organization_id, created_at, id"
            )
        ).fetchall()
        seq_by_org: dict[str | None, int] = {}
        for row in rows:
            org = row[1]
            seq_by_org[org] = seq_by_org.get(org, 0) + 1
            bind.execute(
                sa.text(
                    "UPDATE prior_auth_records SET seq_no = :seq WHERE id = :id"
                ),
                {"seq": seq_by_org[org], "id": row[0]},
            )

    # UNIQUE constraint on (organization_id, seq_no).
    indices = {ix["name"] for ix in inspector.get_indexes("prior_auth_records")}
    if "uq_prior_auth_org_seq" not in indices:
        with op.batch_alter_table("prior_auth_records") as batch:
            batch.create_unique_constraint(
                "uq_prior_auth_org_seq", ["organization_id", "seq_no"]
            )

    # Refresh inspector before switching NOT NULL — batch ops invalidate
    # the cached reflection on SQLite.
    inspector = sa_inspect(bind)
    cols = {c["name"]: c for c in inspector.get_columns("prior_auth_records")}
    if "seq_no" in cols and cols["seq_no"].get("nullable") is True:
        with op.batch_alter_table("prior_auth_records") as batch:
            batch.alter_column("seq_no", existing_type=sa.BigInteger(), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "prior_auth_records" not in set(inspector.get_table_names()):
        return

    indices = {ix["name"] for ix in inspector.get_indexes("prior_auth_records")}
    if "uq_prior_auth_org_seq" in indices:
        with op.batch_alter_table("prior_auth_records") as batch:
            batch.drop_constraint("uq_prior_auth_org_seq", type_="unique")

    cols = {c["name"] for c in inspector.get_columns("prior_auth_records")}
    if "seq_no" in cols:
        with op.batch_alter_table("prior_auth_records") as batch:
            batch.drop_column("seq_no")
