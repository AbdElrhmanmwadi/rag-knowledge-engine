from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from controllers.AgentController import AgentController
from helpers.auth_dependencies import get_current_user
from helpers.config import Settings, get_settings
from helpers.db import get_db
from models.enums.ResponseEnums import ResponseStatus
from models.user_model import User
from routes.schemes.agent import AgentChatRequest
from services.project_access import get_project_for_user


agent_router = APIRouter(
    prefix="/api/v1/agent",
    tags=["api-v1", "agent"],
)


def _controller(request: Request, settings: Settings) -> AgentController:
    return AgentController(
        db_client=request.app.db_client,
        embedding_client=request.app.embedding_client,
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        template_parser=request.app.template_parser,
        default_limit=settings.AGENT_DEFAULT_RETRIEVAL_LIMIT,
        max_history_messages=settings.AGENT_MAX_HISTORY_MESSAGES,
    )


@agent_router.post("/chat/{project_id}")
async def agent_chat(
    request: Request,
    project_id: int,
    chat_request: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    project = await get_project_for_user(
        db,
        project_id=project_id,
        user_id=current_user.id,
        create_if_missing=False,
    )
    result = await _controller(request, settings).chat(
        project=project,
        user=current_user,
        message=chat_request.message,
        session_id=chat_request.session_id,
        limit=chat_request.limit,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.AGENT_CHAT_SUCCESS.value,
            **result,
        },
    )


@agent_router.get("/sessions/{project_id}")
async def list_agent_sessions(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    project = await get_project_for_user(
        db,
        project_id=project_id,
        user_id=current_user.id,
        create_if_missing=False,
    )
    sessions = await _controller(request, settings).list_sessions(project=project, user=current_user)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.AGENT_SESSIONS_SUCCESS.value,
            "sessions": [_serialize_session(session) for session in sessions],
        },
    )


@agent_router.get("/sessions/{project_id}/{session_id}")
async def get_agent_session(
    request: Request,
    project_id: int,
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    project = await get_project_for_user(
        db,
        project_id=project_id,
        user_id=current_user.id,
        create_if_missing=False,
    )
    agent_session = await _controller(request, settings).get_session(
        project=project,
        user=current_user,
        session_id=session_id,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.AGENT_SESSION_SUCCESS.value,
            "session": _serialize_session(agent_session, include_messages=True),
        },
    )


@agent_router.delete("/sessions/{project_id}/{session_id}")
async def delete_agent_session(
    request: Request,
    project_id: int,
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    project = await get_project_for_user(
        db,
        project_id=project_id,
        user_id=current_user.id,
        create_if_missing=False,
    )
    await _controller(request, settings).delete_session(
        project=project,
        user=current_user,
        session_id=session_id,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.AGENT_SESSION_DELETED.value,
            "deleted_session": session_id,
        },
    )


def _serialize_session(agent_session, include_messages: bool = False) -> dict:
    payload = {
        "session_id": agent_session.session_id,
        "project_id": agent_session.project_id,
        "user_id": agent_session.user_id,
        "title": agent_session.title,
        "created_at": agent_session.created_at.isoformat() if agent_session.created_at else None,
        "updated_at": agent_session.updated_at.isoformat() if agent_session.updated_at else None,
    }
    if include_messages:
        payload["messages"] = [
            {
                "message_id": message.message_id,
                "role": message.role,
                "content": message.content,
                "metadata": message.message_metadata or {},
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
            for message in agent_session.messages
        ]
    return payload
