"""mfa columns + mfa_recovery_codes table

Revision ID: 012
Revises: 011
Create Date: 2026-05-04

Sprint 7 Phase C — TOTP-based MFA.

Schema:
- ``users.mfa_secret`` — base32 TOTP shared secret. Cleartext at
  rest today (the row is FK-locked to a single user; encryption
  at rest is the Postgres TDE layer's job). A future migration
  can swap to libsodium-encrypted storage if the threat model
  changes.
- ``users.mfa_enabled`` — toggled to True only after the user
  confirms the TOTP code, so an enrol that's never confirmed
  doesn't lock the user out.
- ``mfa_recovery_codes(id, user_id, code_hash, used_at)`` — 10
  single-use 8-character recovery codes per user; the
  cleartext is shown once at enrol-confirm time. Only sha256
  hashes live in the DB.
"""

from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("mfa_secret", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "code_hash",
            sa.String(length=64),
            nullable=False,
            unique=True,
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


def downgrade() -> None:
    op.drop_table("mfa_recovery_codes")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "mfa_secret")
