"""password_reset_tokens table

Revision ID: 011
Revises: 010
Create Date: 2026-05-04

Sprint 6 — Token-based password reset.

Schema notes:
- ``token_hash`` stores sha256(cleartext_token) hex-encoded so a
  database leak never exposes a usable reset link. The cleartext is
  emailed to the user once and never persisted.
- Indexed on ``token_hash`` for the redeem lookup and on ``user_id``
  for "list active tokens for this user" / cleanup queries.
- ``used_at`` is the single-use marker. A redeemed token cannot be
  re-used; concurrent redeem attempts collide on the index lookup
  and the second sees ``used_at != NULL``.
- ``expires_at`` enforced in code (the issue helper sets a TTL).
  Periodic cleanup of expired+used rows is the scheduler's job
  (added in a follow-up sprint if retention becomes an issue).
"""

from alembic import op
import sqlalchemy as sa


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_tokens_token_hash",
        table_name="password_reset_tokens",
    )
    op.drop_table("password_reset_tokens")
