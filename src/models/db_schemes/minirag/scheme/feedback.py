from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Text, func

from .minirag_base import SQLAlchemyBase


class AnswerFeedback(SQLAlchemyBase):
    """One user rating (👍/👎) on a RAG/agent answer, for quality analytics."""

    __tablename__ = "answer_feedback"

    feedback_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Nullable: direct RAG answers have no agent session. SET NULL keeps the feedback
    # if the session is later deleted.
    session_id = Column(Integer, ForeignKey("agent_sessions.session_id", ondelete="SET NULL"), nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    rating = Column(Integer, nullable=False)  # 1 = 👍 helpful, -1 = 👎 not helpful
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_answer_feedback_project_id", project_id),
        Index("ix_answer_feedback_rating", rating),
    )
