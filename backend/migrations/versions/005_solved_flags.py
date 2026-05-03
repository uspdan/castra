"""solved_flags per-flag attribution table

Revision ID: 005
Revises: 004
Create Date: 2026-05-02

Phase 12 (slice 3) sidecar to ``solves``: each row attributes a single
matched flag to a (user, challenge) pair. The scoreboard still reads
from ``solves`` (per-challenge aggregate); ``solved_flags`` exists so
multi-flag challenges can surface per-flag progress without changing
the scoring contract.

Append-only schema; no backfill. Existing ``solves`` rows from
pre-Phase-12 deployments have no per-flag attribution and are not
re-derived (the original validator output is unavailable). The v1
``GET /challenges/{slug}/progress`` endpoint reports ``captured=true``
on the parent ``Solve`` plus zero per-flag rows for these legacy
solves; clients render this as "fully captured (legacy)".
"""

from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solved_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "challenge_id",
            sa.Integer(),
            sa.ForeignKey("challenges.id"),
            nullable=False,
        ),
        sa.Column("flag_id", sa.String(length=64), nullable=False),
        sa.Column("points_awarded", sa.Integer(), nullable=False),
        sa.Column(
            "is_first_blood_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("validator_name", sa.String(length=64), nullable=True),
        sa.Column(
            "solved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id",
            "challenge_id",
            "flag_id",
            name="uq_solved_flag_user_challenge_flag",
        ),
    )
    op.create_index(
        "ix_solved_flags_user_id", "solved_flags", ["user_id"]
    )
    op.create_index(
        "ix_solved_flags_challenge_id", "solved_flags", ["challenge_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_solved_flags_challenge_id", table_name="solved_flags")
    op.drop_index("ix_solved_flags_user_id", table_name="solved_flags")
    op.drop_table("solved_flags")
