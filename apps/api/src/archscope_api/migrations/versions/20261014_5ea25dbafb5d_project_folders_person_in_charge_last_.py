"""project folders, person in charge, last edited by

Revision ID: 5ea25dbafb5d
Revises: 036f2d859d08
Create Date: 2026-10-14 12:00:27.981267
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5ea25dbafb5d"
down_revision = "036f2d859d08"
branch_labels = None
depends_on = None

_LEAD_FK = "fk_projects_lead_user_id_users"
_EDITOR_FK = "fk_projects_updated_by_users"


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("folder", sa.String(length=120), server_default="", nullable=False))
        batch_op.add_column(sa.Column("lead_user_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("updated_by", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(_LEAD_FK, "users", ["lead_user_id"], ["id"], ondelete="SET NULL")
        batch_op.create_foreign_key(_EDITOR_FK, "users", ["updated_by"], ["id"], ondelete="SET NULL")
    # Existing projects: their creator is in charge and the last known editor.
    op.execute("UPDATE projects SET lead_user_id = created_by, updated_by = created_by WHERE lead_user_id IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint(_EDITOR_FK, type_="foreignkey")
        batch_op.drop_constraint(_LEAD_FK, type_="foreignkey")
        batch_op.drop_column("updated_by")
        batch_op.drop_column("lead_user_id")
        batch_op.drop_column("folder")
