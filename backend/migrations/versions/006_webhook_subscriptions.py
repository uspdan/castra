"""webhook_subscriptions table for admin-managed outbound webhooks

Revision ID: 006
Revises: 005
Create Date: 2026-05-02

Phase 12 (slice 5). Each row is one outbound HTTPS subscription
owned by an admin. The dispatch service POSTs a canonical JSON
envelope to ``target_url`` whenever a configured event fires, with
an HMAC-SHA256 signature header derived from ``secret``.

The ``secret`` column is generated at create time and surfaced to
the admin **once** through the create response — subsequent reads
omit it. This matches the secret-distribution model GitHub / Stripe
use and means a leaked DB doesn't immediately leak signing keys
(the admin would have already saved the secret elsewhere).

Append-only schema; no backfill. The pre-Phase-12 env-var-driven
``SLACK_WEBHOOK_URL`` / ``TEAMS_WEBHOOK_URL`` paths remain in place
so legacy deployments keep delivering to chat channels.
"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_url", sa.String(length=500), nullable=False),
        sa.Column("secret", sa.String(length=128), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=32), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_webhook_subscriptions_owner",
        "webhook_subscriptions",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_webhook_subscriptions_active",
        "webhook_subscriptions",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_subscriptions_active", table_name="webhook_subscriptions"
    )
    op.drop_index(
        "ix_webhook_subscriptions_owner", table_name="webhook_subscriptions"
    )
    op.drop_table("webhook_subscriptions")
