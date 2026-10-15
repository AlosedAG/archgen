"""library files in the database

Revision ID: 4144cca5e6fe
Revises: 94f1e97c4efd
Create Date: 2026-10-14 13:35:32.739196
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "4144cca5e6fe"
down_revision = "94f1e97c4efd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stored_files",
        sa.Column("key", sa.String(length=300), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("stored_files")
