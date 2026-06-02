"""add project owner_id

Revision ID: e3a9f1b2c4d5
Revises: c4e8b1a2d7f0
Create Date: 2026-06-02 00:00:00.000000

Backfill strategy (existing deployments):
  1. Add owner_id as nullable.
  2. Assign every existing project to the user with the smallest users.id
     (typically the first registered account). Requires at least one user row;
     run auth migrations and register a user before upgrading if the DB is empty.
  3. Enforce NOT NULL and add the foreign key to users.id.

New projects created after this migration must set owner_id via the API layer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3a9f1b2c4d5"
down_revision: Union[str, None] = "c4e8b1a2d7f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("owner_id", sa.Integer(), nullable=True))

    connection = op.get_bind()
    default_owner = connection.execute(
        sa.text("SELECT MIN(id) FROM users")
    ).scalar()

    if default_owner is None:
        raise RuntimeError(
            "Cannot add projects.owner_id: no users exist. "
            "Create at least one user (e.g. via /auth/register) before running this migration."
        )

    connection.execute(
        sa.text("UPDATE projects SET owner_id = :owner_id WHERE owner_id IS NULL"),
        {"owner_id": default_owner},
    )

    op.alter_column("projects", "owner_id", nullable=False)
    op.create_index(op.f("ix_projects_owner_id"), "projects", ["owner_id"], unique=False)
    op.create_foreign_key(
        "fk_projects_owner_id_users",
        "projects",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_owner_id_users", "projects", type_="foreignkey")
    op.drop_index(op.f("ix_projects_owner_id"), table_name="projects")
    op.drop_column("projects", "owner_id")
