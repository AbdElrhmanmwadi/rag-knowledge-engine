from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from helpers.auth_dependencies import get_current_user
from models.ProjectModel import ProjectModel
from models.enums.ResponseEnums import ResponseStatus
from models.user_model import User


projects_router = APIRouter(
    prefix="/api/v1/projects",
    tags=["api-v1", "projects"],
)


@projects_router.get("")
async def list_user_projects(
    request: Request,
    current_user: User = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    projects, total_pages, total = await project_model.get_projects_for_owner(
        owner_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.PROJECT_LIST_SUCCESS.value,
            "projects": [
                {
                    "project_id": project.project_id,
                    "project_uuid": str(project.project_uuid),
                    "created_at": project.created_at.isoformat() if project.created_at else None,
                    "updated_at": project.updated_at.isoformat() if project.updated_at else None,
                }
                for project in projects
            ],
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total": total,
        },
    )
