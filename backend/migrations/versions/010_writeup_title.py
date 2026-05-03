"""writeups.title column

Revision ID: 010
Revises: 009
Create Date: 2026-05-03

The writeups router (``POST /writeups/{slug}``) and the v1 schemas
(``WriteupCreate.title`` / ``WriteupListItem.title``) both depend on
a ``title`` field, but the SQLAlchemy ``Writeup`` model + initial
migration never added one. Submitting a writeup via the legacy
endpoint therefore raises ``TypeError: 'title' is an invalid keyword
argument for Writeup`` at the ORM layer.

This migration backfills the column. Existing rows take an empty
string default (none have been writeable since the bug shipped); the
NOT NULL constraint is added after the default seeding so the table
stays consistent.
"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "writeups",
        sa.Column(
            "title",
            sa.String(length=200),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("writeups", "title")
