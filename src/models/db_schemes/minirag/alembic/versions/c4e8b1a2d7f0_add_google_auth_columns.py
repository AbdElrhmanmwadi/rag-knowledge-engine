"""add google auth columns

Revision ID: c4e8b1a2d7f0
Revises: a1f7c2d9e8b3
Create Date: 2026-05-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8b1a2d7f0"
down_revision: Union[str, None] = "a1f7c2d9e8b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_id", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(length=20), server_default="local", nullable=False),
    )
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=True)
    op.create_index(op.f("ix_users_google_id"), "users", ["google_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_google_id"), table_name="users")
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "google_id")
