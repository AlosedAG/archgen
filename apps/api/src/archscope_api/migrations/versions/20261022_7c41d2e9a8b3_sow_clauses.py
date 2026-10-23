"""sow clauses

Revision ID: 7c41d2e9a8b3
Revises: 3122ab193f41
Create Date: 2026-10-22 16:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "7c41d2e9a8b3"
down_revision = "3122ab193f41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sow_clauses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("include_by_default", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sow_clauses", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sow_clauses_workspace_id"), ["workspace_id"], unique=False)
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.add_column(sa.Column("clauses_seeded", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.drop_column("clauses_seeded")
    with op.batch_alter_table("sow_clauses", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sow_clauses_workspace_id"))

    op.drop_table("sow_clauses")
