from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from .minirag_base import SQLAlchemyBase


class TranslationJob(SQLAlchemyBase):
    __tablename__ = "translation_jobs"

    job_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False)
    source_lang = Column(String, nullable=False, default="auto")
    target_lang = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    result_asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="SET NULL"), nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    project = relationship("Project", back_populates="translation_jobs", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_translation_jobs_project_id", project_id),
        Index("ix_translation_jobs_asset_id", asset_id),
        Index("ix_translation_jobs_status", status),
    )
