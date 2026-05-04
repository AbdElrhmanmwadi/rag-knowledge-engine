from .minirag_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
class Project(SQLAlchemyBase):
    __tablename__ = "projects"
    project_id = Column(Integer, primary_key=True, index=True)
    project_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(),nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    chunks = relationship("DataChunk", back_populates="project", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan")
    translation_jobs = relationship("TranslationJob", back_populates="project", cascade="all, delete-orphan")

    
