"""orchestration profile columns on challenge_instances

Revision ID: 004
Revises: 003
Create Date: 2026-05-02

Adds the per-instance audit fields recorded by the Phase 9 launcher:

  - ``applied_profile`` (e.g. ``default-strict``, ``malware-sandbox``,
    ``egress-proxied``) — name of the launch profile that decided the
    container's security envelope.
  - ``applied_digest`` (``sha256:<64hex>``) — image digest the launcher
    actually pinned to. Phase 9 refuses to launch without one, so all
    new rows have a digest; older rows from pre-Phase-9 deployments may
    be ``NULL`` (they were never digest-pinned at the time).
  - ``seccomp_profile_sha256`` — SHA-256 of the bundled seccomp JSON
    that was applied. Lets the audit chain prove which profile-bytes
    were running, not just which name.

The migration is append-only: existing rows take the
``default-strict`` server default for ``applied_profile`` so the
``NOT NULL`` constraint is satisfied without a backfill step.
"""

from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "challenge_instances",
        sa.Column(
            "applied_profile",
            sa.String(length=64),
            nullable=False,
            server_default="default-strict",
        ),
    )
    op.add_column(
        "challenge_instances",
        sa.Column("applied_digest", sa.String(length=71), nullable=True),
    )
    op.add_column(
        "challenge_instances",
        sa.Column(
            "seccomp_profile_sha256", sa.String(length=64), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("challenge_instances", "seccomp_profile_sha256")
    op.drop_column("challenge_instances", "applied_digest")
    op.drop_column("challenge_instances", "applied_profile")
