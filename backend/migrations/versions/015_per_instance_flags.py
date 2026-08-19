"""Per-instance flags (ADR 005 part 2).

``challenge_flags.per_instance`` marks exact flags whose value is
minted per launch; ``challenge_instances.flag_hashes`` stores the
minted hashes ({flag_id: sha256}). Cleartext lives only in the
container environment.

Revision ID: 015
Revises: 014
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "challenge_flags",
        sa.Column(
            "per_instance",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "challenge_instances",
        sa.Column("flag_hashes", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("challenge_instances", "flag_hashes")
    op.drop_column("challenge_flags", "per_instance")
