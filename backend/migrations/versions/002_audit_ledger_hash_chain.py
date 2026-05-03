"""audit_ledger hash chain

Revision ID: 002
Revises: 001
Create Date: 2026-05-02

Adds the append-only `audit_ledger` table introduced by Phase 2 of the
hardening programme. The legacy `audit_logs` table is left untouched (the
scheduler still reaps it on a 90-day cutoff). New code writes to
`audit_ledger` only.

The chain is enforced at three layers:
  1. Application: services/audit/ledger.py is the single writer.
  2. DB-level uniqueness on (seq) and (this_hash).
  3. DB-level trigger that refuses UPDATE / DELETE on every row.
"""

from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_ledger",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("this_hash", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("seq", name="uq_audit_ledger_seq"),
        sa.UniqueConstraint("this_hash", name="uq_audit_ledger_this_hash"),
        sa.CheckConstraint("seq >= 1", name="ck_audit_ledger_seq_positive"),
        sa.CheckConstraint("char_length(prev_hash) = 64", name="ck_audit_ledger_prev_hash_len"),
        sa.CheckConstraint("char_length(this_hash) = 64", name="ck_audit_ledger_this_hash_len"),
    )
    op.create_index(
        "ix_audit_ledger_event_type", "audit_ledger", ["event_type"]
    )
    op.create_index(
        "ix_audit_ledger_actor", "audit_ledger", ["actor_type", "actor_id"]
    )
    op.create_index(
        "ix_audit_ledger_created_at", "audit_ledger", ["created_at"]
    )

    # Immutability: refuse any UPDATE or DELETE on the ledger table.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_ledger_immutable()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_ledger is append-only (op=%)', TG_OP
                USING ERRCODE = 'check_violation';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_ledger_no_update
        BEFORE UPDATE ON audit_ledger
        FOR EACH ROW EXECUTE FUNCTION audit_ledger_immutable();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_ledger_no_delete
        BEFORE DELETE ON audit_ledger
        FOR EACH ROW EXECUTE FUNCTION audit_ledger_immutable();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_ledger_no_delete ON audit_ledger;")
    op.execute("DROP TRIGGER IF EXISTS audit_ledger_no_update ON audit_ledger;")
    op.execute("DROP FUNCTION IF EXISTS audit_ledger_immutable();")
    op.drop_index("ix_audit_ledger_created_at", table_name="audit_ledger")
    op.drop_index("ix_audit_ledger_actor", table_name="audit_ledger")
    op.drop_index("ix_audit_ledger_event_type", table_name="audit_ledger")
    op.drop_table("audit_ledger")
