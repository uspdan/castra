"""webhook_deliveries history table

Revision ID: 007
Revises: 006
Create Date: 2026-05-02

Phase 12 (slice 6). One row per outbound dispatch attempt; the
v1 list-deliveries endpoint paginates this table and the replay
endpoint reads the canonical payload back to re-sign and re-POST.

Append-only; the slice doesn't ship a retention scheduler. Future
work can add a scheduler-driven prune job once we have data on
typical row counts.
"""

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("delivery_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("response_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_webhook_deliveries_subscription_created",
        "webhook_deliveries",
        ["subscription_id", "created_at"],
    )
    op.create_index(
        "ix_webhook_deliveries_delivery_id",
        "webhook_deliveries",
        ["delivery_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_deliveries_delivery_id", table_name="webhook_deliveries"
    )
    op.drop_index(
        "ix_webhook_deliveries_subscription_created",
        table_name="webhook_deliveries",
    )
    op.drop_table("webhook_deliveries")
