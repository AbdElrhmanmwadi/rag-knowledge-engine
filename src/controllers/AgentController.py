import asyncio
import logging

from fastapi import HTTPException, status

from controllers.NLPController import NLPController
from models.AgentSessionModel import AgentSessionModel
from models.db_schemes.minirag.scheme import Project
from models.user_model import User
from services.agent_service import AgentService
from services.agent_tools import AgentTools

logger = logging.getLogger(__name__)


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

    async def _prepare_session(
        self,
        project: Project,
        user: User,
        message: str,
        session_id: int | None,
    ):
        """Create or load the session and return (session_model, session, history)."""
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

        return session_model, agent_session, history

    async def chat(
        self,
        project: Project,
        user: User,
        message: str,
        session_id: int | None = None,
        limit: int | None = None,
    ) -> dict:
        session_model, agent_session, history = await self._prepare_session(
            project=project, user=user, message=message, session_id=session_id
        )
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

    async def chat_stream(
        self,
        project: Project,
        user: User,
        message: str,
        session_id: int | None = None,
        limit: int | None = None,
    ):
        """Yield {"event", "data"} dicts for the SSE route: meta, delta*, done.

        Mirrors chat(): the user message is persisted up front, the assistant
        message exactly once after the stream finishes — never a partial answer.
        """
        session_model, agent_session, history = await self._prepare_session(
            project=project, user=user, message=message, session_id=session_id
        )
        await session_model.add_message(
            session_id=agent_session.session_id,
            role="user",
            content=message,
        )

        sources: list = []
        tool_trace: list = []
        answer_parts: list[str] = []
        try:
            async for event in self.agent_service.run_stream(
                project=project,
                message=message,
                limit=limit or self.default_limit,
                history=history,
            ):
                if event["type"] == "meta":
                    sources = event["sources"]
                    tool_trace = event["tool_trace"]
                    yield {
                        "event": "meta",
                        "data": {
                            "session_id": agent_session.session_id,
                            "sources": sources,
                            "tool_trace": tool_trace,
                        },
                    }
                elif event["type"] == "delta":
                    answer_parts.append(event["text"])
                    yield {"event": "delta", "data": {"text": event["text"]}}
                elif event["type"] == "final":
                    # Completed trace (includes the rag_answer entry that did not
                    # exist yet when meta was sent) — persisted, not re-emitted.
                    tool_trace = event["tool_trace"]
        except (GeneratorExit, asyncio.CancelledError):
            # Client disconnected mid-stream: do not persist a partial answer.
            raise
        except Exception:
            logger.exception("Agent stream failed mid-generation")
            yield {"event": "error", "data": {"detail": "Generation failed mid-stream"}}
            return

        answer = "".join(answer_parts).strip()
        if not answer:
            # Keep session history consistent with the non-stream fallback.
            answer = "I could not generate an answer from the retrieved project context."

        # Persist before emitting "done" so a disconnect on the last event can
        # never lose the completed answer.
        await session_model.add_message(
            session_id=agent_session.session_id,
            role="assistant",
            content=answer,
            metadata={
                "sources": sources,
                "tool_trace": tool_trace,
            },
        )
        yield {"event": "done", "data": {"answer": answer}}

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
