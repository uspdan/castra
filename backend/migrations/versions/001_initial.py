"""Initial migration

Revision ID: 001
Revises:
Create Date: 2024-03-15
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("username", sa.String(100), unique=True, index=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("role", sa.Enum("operator", "admin", name="userrole"), default="operator", nullable=False),
        sa.Column("team", sa.Enum("red", "blue", name="teamtype"), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("onboarding_completed", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "challenges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(200), unique=True, index=True, nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), index=True, nullable=False),
        sa.Column("team", sa.Enum("red", "blue", name="teamtype", create_type=False), index=True, nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("flag_hash", sa.String(64), nullable=False),
        sa.Column("hints", sa.JSON(), default=[]),
        sa.Column("skills", sa.JSON(), default=[]),
        sa.Column("mitre_techniques", sa.JSON(), default=[]),
        sa.Column("docker_image", sa.String(300), nullable=False),
        sa.Column("docker_port", sa.Integer(), nullable=False),
        sa.Column("docker_config", sa.JSON(), default={}),
        sa.Column("prerequisite_ids", sa.JSON(), default=[]),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("is_released", sa.Boolean(), default=False, nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_challenges_team_category", "challenges", ["team", "category"])

    op.create_table(
        "solves",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id"), nullable=False),
        sa.Column("points_awarded", sa.Integer(), nullable=False),
        sa.Column("hint_used", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_first_blood", sa.Boolean(), default=False, nullable=False),
        sa.Column("time_to_solve", sa.Integer(), nullable=True),
        sa.Column("solved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "challenge_id", name="uq_solve_user_challenge"),
    )

    op.create_table(
        "hint_unlocks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id"), nullable=False),
        sa.Column("hint_index", sa.Integer(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "challenge_id", "hint_index", name="uq_hint_user_challenge_index"),
    )

    op.create_table(
        "challenge_instances",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id"), nullable=False),
        sa.Column("container_id", sa.String(100), nullable=True),
        sa.Column("container_name", sa.String(200), nullable=True),
        sa.Column("status", sa.Enum("pending", "running", "stopped", "failed", name="instancestatus"), nullable=False),
        sa.Column("assigned_ip", sa.String(50), nullable=True),
        sa.Column("assigned_port", sa.Integer(), nullable=True),
        sa.Column("network_name", sa.String(200), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_instance_user_status", "challenge_instances", ["user_id", "status"])

    op.create_table(
        "writeups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rating", sa.Float(), default=0.0),
        sa.Column("rating_count", sa.Integer(), default=0),
        sa.Column("is_approved", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "challenge_id", name="uq_writeup_user_challenge"),
    )

    op.create_table(
        "streaks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("current_streak", sa.Integer(), default=0, nullable=False),
        sa.Column("longest_streak", sa.Integer(), default=0, nullable=False),
        sa.Column("last_solve_date", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "competitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("challenge_ids", sa.JSON(), default=[]),
        sa.Column("is_active", sa.Boolean(), default=False, nullable=False),
        sa.Column("hints_disabled", sa.Boolean(), default=True, nullable=False),
        sa.Column("format", sa.String(50), default="jeopardy"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), index=True, nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), index=True, nullable=False),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("notification_type", sa.String(50), default="info"),
        sa.Column("is_global", sa.Boolean(), default=False, nullable=False),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_read", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "learning_paths",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("team", sa.String(10), nullable=False),
        sa.Column("difficulty_range", sa.JSON(), default={}),
        sa.Column("challenge_order", sa.JSON(), default=[]),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "challenge_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id"), nullable=False),
        sa.Column("difficulty_rating", sa.Integer(), nullable=False),
        sa.Column("quality_rating", sa.Integer(), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "challenge_id", name="uq_feedback_user_challenge"),
    )


def downgrade() -> None:
    op.drop_table("challenge_feedback")
    op.drop_table("learning_paths")
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("competitions")
    op.drop_table("streaks")
    op.drop_table("writeups")
    op.drop_table("challenge_instances")
    op.drop_table("hint_unlocks")
    op.drop_table("solves")
    op.drop_table("challenges")
    op.drop_table("users")
