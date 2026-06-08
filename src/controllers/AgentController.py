from fastapi import HTTPException, status

from controllers.NLPController import NLPController
from models.AgentSessionModel import AgentSessionModel
from models.db_schemes.minirag.scheme import Project
from models.user_model import User
from services.agent_service import AgentService
from services.agent_tools import AgentTools


class AgentController:
    def __init__(
        self,
        db_client,
        embedding_client,
        vectordb_client,
        generation_client,
        template_parser,
        default_limit: int = 5,
        max_history_messages: int = 10,
    ):
        nlp_controller = NLPController(
            embedding_client=embedding_client,
            vectordb_client=vectordb_client,
            generation_client=generation_client,
            template_parser=template_parser,
        )
        tools = AgentTools(db_client=db_client, nlp_controller=nlp_controller)
        self.db_client = db_client
        self.default_limit = default_limit
        self.max_history_messages = max_history_messages
        self.agent_service = AgentService(tools=tools, default_limit=default_limit)

    async def chat(
        self,
        project: Project,
        user: User,
        message: str,
        session_id: int | None = None,
        limit: int | None = None,
    ) -> dict:
        session_model = await AgentSessionModel.create_instance(db_client=self.db_client)
        history: list[dict] = []
        if session_id is None:
            agent_session = await session_model.create_session(
                project_id=project.project_id,
                user_id=user.id,
                title=self._build_title(message),
            )
        else:
            agent_session = await session_model.get_session(
                session_id=session_id,
                project_id=project.project_id,
                user_id=user.id,
            )
            if agent_session is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent session not found",
                )
            # Captured before persisting the current message, so it is not duplicated.
            history = [
                {"role": m.role, "content": m.content}
                for m in agent_session.messages
            ]

        if self.max_history_messages > 0:
            history = history[-self.max_history_messages:]

        await session_model.add_message(
            session_id=agent_session.session_id,
            role="user",
            content=message,
        )
        result = await self.agent_service.run(
            project=project,
            message=message,
            limit=limit or self.default_limit,
            history=history,
        )
        await session_model.add_message(
            session_id=agent_session.session_id,
            role="assistant",
            content=result["answer"],
            metadata={
                "sources": result["sources"],
                "tool_trace": result["tool_trace"],
            },
        )
        return {
            "session_id": agent_session.session_id,
            **result,
        }

    async def list_sessions(self, project: Project, user: User) -> list:
        session_model = await AgentSessionModel.create_instance(db_client=self.db_client)
        return await session_model.list_sessions(project_id=project.project_id, user_id=user.id)

    async def get_session(self, project: Project, user: User, session_id: int):
        session_model = await AgentSessionModel.create_instance(db_client=self.db_client)
        agent_session = await session_model.get_session(
            session_id=session_id,
            project_id=project.project_id,
            user_id=user.id,
        )
        if agent_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent session not found",
            )
        return agent_session

    async def delete_session(self, project: Project, user: User, session_id: int) -> bool:
        session_model = await AgentSessionModel.create_instance(db_client=self.db_client)
        deleted = await session_model.delete_session(
            session_id=session_id,
            project_id=project.project_id,
            user_id=user.id,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent session not found",
            )
        return True

    def _build_title(self, message: str) -> str:
        title = " ".join(message.strip().split())
        if not title:
            return "Agent session"
        return title[:120]
