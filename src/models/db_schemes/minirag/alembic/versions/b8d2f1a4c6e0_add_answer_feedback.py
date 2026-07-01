"""add answer feedback

Revision ID: b8d2f1a4c6e0
Revises: f4b7c2a8d901
Create Date: 2026-07-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8d2f1a4c6e0"
down_revision: Union[str, None] = "f4b7c2a8d901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "answer_feedback",
        sa.Column("feedback_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.session_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("feedback_id"),
    )
    op.create_index("ix_answer_feedback_project_id", "answer_feedback", ["project_id"], unique=False)
    op.create_index("ix_answer_feedback_rating", "answer_feedback", ["rating"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_answer_feedback_rating", table_name="answer_feedback")
    op.drop_index("ix_answer_feedback_project_id", table_name="answer_feedback")
    op.drop_table("answer_feedback")
