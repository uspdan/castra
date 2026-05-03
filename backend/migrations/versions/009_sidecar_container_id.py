"""sidecar_container_id on challenge_instances

Revision ID: 009
Revises: 008
Create Date: 2026-05-03

Adds the per-instance egress-proxy sidecar tracking column. When the
launcher resolves the ``egress-proxied-sidecar`` profile it spawns a
dedicated tinyproxy container alongside the challenge; the cleanup
path needs to find and remove that container by id, even if the
sidecar's name has rotated.

Append-only — existing rows take ``NULL`` (no sidecar was ever
spawned for them).
"""

from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "challenge_instances",
        sa.Column("sidecar_container_id", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("challenge_instances", "sidecar_container_id")
