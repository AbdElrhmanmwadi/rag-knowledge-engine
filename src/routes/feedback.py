from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.auth_dependencies import get_current_user
from helpers.db import get_db
from models.FeedbackModel import FeedbackModel
from models.enums.ResponseEnums import ResponseStatus
from models.user_model import User
from routes.schemes.feedback import FeedbackRequest
from services.project_access import get_project_for_user


feedback_router = APIRouter(
    prefix="/api/v1/feedback",
    tags=["api-v1", "feedback"],
)


@feedback_router.post("/{project_id}")
async def submit_feedback(
    request: Request,
    project_id: int,
    feedback_request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_for_user(
        db, project_id=project_id, user_id=current_user.id, create_if_missing=False
    )

    if feedback_request.rating not in (1, -1):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseStatus.FEEDBACK_INVALID_RATING.value,
                "message": "rating must be 1 (helpful) or -1 (not helpful)",
            },
        )

    feedback_model = await FeedbackModel.create_instance(db_client=request.app.db_client)
    feedback = await feedback_model.add_feedback(
        project_id=project.project_id,
        user_id=current_user.id,
        question=feedback_request.question,
        answer=feedback_request.answer,
        rating=feedback_request.rating,
        session_id=feedback_request.session_id,
        comment=feedback_request.comment,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.FEEDBACK_SUCCESS.value,
            "feedback_id": feedback.feedback_id,
        },
    )


@feedback_router.get("/{project_id}/analytics")
async def feedback_analytics(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    top_n: int = Query(default=10, ge=1, le=50),
):
    project = await get_project_for_user(
        db, project_id=project_id, user_id=current_user.id, create_if_missing=False
    )

    feedback_model = await FeedbackModel.create_instance(db_client=request.app.db_client)
    analytics = await feedback_model.get_analytics(project_id=project.project_id, top_n=top_n)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.FEEDBACK_ANALYTICS_SUCCESS.value,
            **analytics,
        },
    )
