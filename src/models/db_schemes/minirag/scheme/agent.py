from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .minirag_base import SQLAlchemyBase


class AgentSession(SQLAlchemyBase):
    __tablename__ = "agent_sessions"

    session_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    project = relationship("Project")
    user = relationship("User")
    messages = relationship(
        "AgentMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AgentMessage.created_at",
    )

    __table_args__ = (
        Index("ix_agent_sessions_project_id", project_id),
        Index("ix_agent_sessions_user_id", user_id),
        Index("ix_agent_sessions_project_user", project_id, user_id),
    )


class AgentMessage(SQLAlchemyBase):
    __tablename__ = "agent_messages"

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("agent_sessions.session_id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    message_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("AgentSession", back_populates="messages")

    __table_args__ = (
        Index("ix_agent_messages_session_id", session_id),
        Index("ix_agent_messages_role", role),
    )
