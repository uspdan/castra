"""Allow NULL docker_image / docker_port for artifact-only challenges.

Spec v1.1 (ADR 005) makes ``container:`` optional in the manifest. A
challenge with no container is served as downloadable artifacts and
never touches the orchestrator, so the image and port columns must
admit NULL.

Revision ID: 014
Revises: 013
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "challenges", "docker_image",
        existing_type=sa.String(length=300), nullable=True,
    )
    op.alter_column(
        "challenges", "docker_port",
        existing_type=sa.Integer(), nullable=True,
    )


def downgrade() -> None:
    # Rows created as artifact-only would violate NOT NULL on the way
    # back. Give them a sentinel image so the downgrade is mechanical;
    # such rows are not launchable either way (there is no image called
    # "artifact-only"), so this cannot make anything *more* runnable.
    op.execute(
        "UPDATE challenges SET docker_image = 'artifact-only', docker_port = 0 "
        "WHERE docker_image IS NULL"
    )
    op.alter_column(
        "challenges", "docker_port",
        existing_type=sa.Integer(), nullable=False,
    )
    op.alter_column(
        "challenges", "docker_image",
        existing_type=sa.String(length=300), nullable=False,
    )
