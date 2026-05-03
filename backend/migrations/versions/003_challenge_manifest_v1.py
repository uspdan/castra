"""challenge manifest v1 columns + flags / artifacts tables

Revision ID: 003
Revises: 002
Create Date: 2026-05-02

Adds the schema needed by Phase 7 of the hardening programme to
support the bluerange-spec v1 manifest format.

Changes to ``challenges``:
  - new columns ``spec_version``, ``manifest_sha256``, ``source_path``,
    ``loaded_at``, ``pending_review``, ``license``, ``author_json``.
  - ``flag_hash`` is relaxed to nullable: v1 challenges declare flags
    via the new ``flags`` table (typed for the validator registry
    landing in Phase 8). Legacy challenges seeded from the flat
    ``challenge.json`` continue to populate ``flag_hash`` directly.

New tables:
  - ``challenge_flags``: typed flag definitions per challenge. Cleartext
    is stored only for non-exact validator types (``regex`` pattern,
    ``multi_part`` parts list); exact-equality flags are kept as
    SHA-256 in ``value_hash`` exactly as before.
  - ``challenge_artifacts``: per-artifact path + sha256 manifest record.
"""

from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "challenges",
        sa.Column("spec_version", sa.String(8), nullable=True),
    )
    op.add_column(
        "challenges",
        sa.Column("manifest_sha256", sa.String(64), nullable=True),
    )
    op.add_column(
        "challenges",
        sa.Column("source_path", sa.String(500), nullable=True),
    )
    op.add_column(
        "challenges",
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "challenges",
        sa.Column(
            "pending_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "challenges",
        sa.Column("license", sa.String(100), nullable=True),
    )
    op.add_column(
        "challenges",
        sa.Column("author_json", sa.JSON(), nullable=True),
    )
    op.alter_column(
        "challenges",
        "flag_hash",
        existing_type=sa.String(64),
        nullable=True,
    )

    op.create_table(
        "challenge_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "challenge_id",
            sa.Integer(),
            sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("flag_id", sa.String(64), nullable=False),
        sa.Column("flag_type", sa.String(32), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("value_hash", sa.String(64), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "challenge_id", "flag_id", name="uq_challenge_flag_id"
        ),
        sa.CheckConstraint("points >= 0", name="ck_challenge_flag_points_non_negative"),
    )
    op.create_index(
        "ix_challenge_flags_challenge_id",
        "challenge_flags",
        ["challenge_id"],
    )

    op.create_table(
        "challenge_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "challenge_id",
            sa.Integer(),
            sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "challenge_id", "path", name="uq_challenge_artifact_path"
        ),
        sa.CheckConstraint(
            "char_length(sha256) = 64",
            name="ck_challenge_artifact_sha256_len",
        ),
    )
    op.create_index(
        "ix_challenge_artifacts_challenge_id",
        "challenge_artifacts",
        ["challenge_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_challenge_artifacts_challenge_id", table_name="challenge_artifacts"
    )
    op.drop_table("challenge_artifacts")
    op.drop_index(
        "ix_challenge_flags_challenge_id", table_name="challenge_flags"
    )
    op.drop_table("challenge_flags")

    # Restore the NOT NULL on flag_hash. Down-migration will fail if v1
    # rows exist with NULL flag_hash; that is intentional — operators
    # must back out v1 data before reverting the schema.
    op.alter_column(
        "challenges",
        "flag_hash",
        existing_type=sa.String(64),
        nullable=False,
    )
    op.drop_column("challenges", "author_json")
    op.drop_column("challenges", "license")
    op.drop_column("challenges", "pending_review")
    op.drop_column("challenges", "loaded_at")
    op.drop_column("challenges", "source_path")
    op.drop_column("challenges", "manifest_sha256")
    op.drop_column("challenges", "spec_version")
