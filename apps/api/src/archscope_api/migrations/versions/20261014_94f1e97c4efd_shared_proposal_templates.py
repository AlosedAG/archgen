"""shared proposal templates

Revision ID: 94f1e97c4efd
Revises: 5ea25dbafb5d
Create Date: 2026-10-14 12:33:55.718048
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "94f1e97c4efd"
down_revision = "5ea25dbafb5d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_proposal_template_workspace_name"),
    )
    with op.batch_alter_table("proposal_templates", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_proposal_templates_workspace_id"), ["workspace_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("proposal_templates", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_proposal_templates_workspace_id"))

    op.drop_table("proposal_templates")
