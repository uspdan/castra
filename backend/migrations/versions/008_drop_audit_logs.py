"""drop legacy audit_logs table

Revision ID: 008
Revises: 007
Create Date: 2026-05-02

Phase 12 (slice 8). Phase 2 introduced the hash-chained
``audit_ledger`` and the legacy ``audit_logs`` table has been
write-redundant ever since. Slice 8 stops the writes, migrates the
admin reads to the ledger, and drops the table here.

The downgrade re-creates the schema (matching ``001_initial.py``)
for emergency rollback, but the data is gone — operators relying on
``audit_logs`` history must read from ``audit_ledger`` instead.
"""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("audit_logs")


def downgrade() -> None:
    # Schema restored from 001_initial.py for emergency rollback.
    # Existing rows are NOT recovered.
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), index=True, nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            index=True,
            nullable=False,
        ),
    )
