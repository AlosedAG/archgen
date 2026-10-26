"""workspace states

Revision ID: 5a9e3c1b7d24
Revises: 7c41d2e9a8b3
Create Date: 2026-10-26 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5a9e3c1b7d24"
down_revision = "7c41d2e9a8b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_states",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "module"),
    )


def downgrade() -> None:
    op.drop_table("workspace_states")
