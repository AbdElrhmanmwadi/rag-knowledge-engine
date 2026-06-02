"""add translation jobs table

Revision ID: a1f7c2d9e8b3
Revises: 9d6f8a2c4b91
Create Date: 2026-05-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1f7c2d9e8b3"
down_revision: Union[str, None] = "9d6f8a2c4b91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "translation_jobs",
        sa.Column("job_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("source_lang", sa.String(), nullable=False),
        sa.Column("target_lang", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("result_asset_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["result_asset_id"], ["assets.asset_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_translation_jobs_asset_id", "translation_jobs", ["asset_id"], unique=False)
    op.create_index("ix_translation_jobs_project_id", "translation_jobs", ["project_id"], unique=False)
    op.create_index("ix_translation_jobs_status", "translation_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_translation_jobs_status", table_name="translation_jobs")
    op.drop_index("ix_translation_jobs_project_id", table_name="translation_jobs")
    op.drop_index("ix_translation_jobs_asset_id", table_name="translation_jobs")
    op.drop_table("translation_jobs")
