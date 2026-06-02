"""Project authorization helpers.

Ownership is enforced via ``owner_id`` today. Extend ``user_has_project_access``
when adding ``project_members`` / roles without changing route handlers.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_schemes.minirag.scheme import Project
from models.db_schemes.minirag.scheme.translation_job import TranslationJob


def user_has_project_access(project: Project, user_id: int) -> bool:
    """Return True if the user may access this project (owner-only for now)."""
    # Future: membership / role checks (e.g. project_members table).
    return project.owner_id == user_id


def check_project_access(project: Project, user_id: int) -> None:
    if not user_has_project_access(project, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this project",
        )


async def get_project_for_user(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    *,
    create_if_missing: bool = False,
) -> Project:
    """Load a project the user may access, optionally creating it for the owner."""
    project = await db.scalar(select(Project).where(Project.project_id == project_id))

    if project is None:
        if not create_if_missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        project = Project(project_id=project_id, owner_id=user_id)
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    check_project_access(project, user_id)
    return project


async def get_translation_job_for_user(
    db: AsyncSession,
    job_id: int,
    user_id: int,
) -> TranslationJob:
    translation_job = await db.scalar(
        select(TranslationJob).where(TranslationJob.job_id == job_id)
    )
    if translation_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation job not found",
        )

    await get_project_for_user(
        db,
        translation_job.project_id,
        user_id,
        create_if_missing=False,
    )
    return translation_job
