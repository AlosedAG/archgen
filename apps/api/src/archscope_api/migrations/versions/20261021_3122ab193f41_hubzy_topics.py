"""hubzy topics

Revision ID: 3122ab193f41
Revises: 4144cca5e6fe
Create Date: 2026-10-21 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "3122ab193f41"
down_revision = "4144cca5e6fe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hubzy_topics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("page", sa.String(length=80), nullable=False),
        sa.Column("question", sa.String(length=300), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("hubzy_topics", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_hubzy_topics_workspace_id"), ["workspace_id"], unique=False)
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hubzy_seeded", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.drop_column("hubzy_seeded")
    with op.batch_alter_table("hubzy_topics", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_hubzy_topics_workspace_id"))

    op.drop_table("hubzy_topics")
