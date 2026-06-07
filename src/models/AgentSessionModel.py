from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from models.db_schemes.minirag.scheme.agent import AgentMessage, AgentSession

from .BaseDataModle import BaseDataModel


class AgentSessionModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client):
        return cls(db_client)

    async def create_session(self, project_id: int, user_id: int, title: str) -> AgentSession:
        async with self.db_client() as session:
            agent_session = AgentSession(project_id=project_id, user_id=user_id, title=title)
            session.add(agent_session)
            await session.commit()
            await session.refresh(agent_session)
            return agent_session

    async def list_sessions(self, project_id: int, user_id: int) -> list[AgentSession]:
        async with self.db_client() as session:
            result = await session.execute(
                select(AgentSession)
                .where(AgentSession.project_id == project_id, AgentSession.user_id == user_id)
                .order_by(AgentSession.updated_at.desc(), AgentSession.created_at.desc())
            )
            return result.scalars().all()

    async def get_session(self, session_id: int, project_id: int, user_id: int) -> AgentSession | None:
        async with self.db_client() as session:
            result = await session.execute(
                select(AgentSession)
                .where(
                    AgentSession.session_id == session_id,
                    AgentSession.project_id == project_id,
                    AgentSession.user_id == user_id,
                )
                .options(selectinload(AgentSession.messages))
            )
            return result.scalar_one_or_none()

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> AgentMessage:
        async with self.db_client() as session:
            message = AgentMessage(
                session_id=session_id,
                role=role,
                content=content,
                message_metadata=metadata or {},
            )
            session.add(message)
            agent_session = await session.get(AgentSession, session_id)
            if agent_session is not None:
                agent_session.updated_at = func.now()
            await session.commit()
            await session.refresh(message)
            return message

    async def delete_session(self, session_id: int, project_id: int, user_id: int) -> bool:
        async with self.db_client() as session:
            result = await session.execute(
                delete(AgentSession).where(
                    AgentSession.session_id == session_id,
                    AgentSession.project_id == project_id,
                    AgentSession.user_id == user_id,
                )
            )
            await session.commit()
            return (result.rowcount or 0) > 0
