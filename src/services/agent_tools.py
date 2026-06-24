from dataclasses import dataclass
from typing import Any

from controllers.NLPController import NLPController
from models.AssetModel import AssetModel
from models.db_schemes.minirag.scheme import Project
from models.enums.AssetTypeEnum import AssetTypeEnum


@dataclass
class AgentToolResult:
    name: str
    status: str
    summary: str
    data: Any = None


class AgentTools:
    def __init__(self, db_client, nlp_controller: NLPController):
        self.db_client = db_client
        self.nlp_controller = nlp_controller

    async def list_project_files(self, project: Project) -> AgentToolResult:
        asset_model = await AssetModel.create_instance(db_client=self.db_client)
        records = await asset_model.get_all_project_asset(
            asset_project_id=project.project_id,
            asset_type=AssetTypeEnum.FILE.value,
        )
        files = [
            {
                "asset_id": record.asset_id,
                "file_id": record.asset_name,
                "file_size": record.asset_size,
                "file_type": record.asset_type,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
            for record in records
        ]
        return AgentToolResult(
            name="list_project_files",
            status="success",
            summary=f"Found {len(files)} project file(s)",
            data=files,
        )

    async def rewrite_query(self, query: str, history: list | None = None) -> AgentToolResult:
        standalone = await self.nlp_controller.condense_query(query=query, history=history)
        standalone = (standalone or query).strip()
        changed = standalone != query.strip()
        return AgentToolResult(
            name="rewrite_query",
            status="success",
            summary=(
                f"Rewrote follow-up to: {standalone}" if changed else "Query already standalone"
            ),
            data=standalone,
        )

    async def rag_search(
        self, project: Project, query: str, limit: int, query_vector=None
    ) -> AgentToolResult:
        documents = await self.nlp_controller.search_in_vectordb(
            project=project,
            text=query,
            limit=limit,
            query_vector=query_vector,
        )
        if documents is False or documents is None:
            documents = []
        return AgentToolResult(
            name="rag_search",
            status="success",
            summary=f"Retrieved {len(documents)} document chunk(s)",
            data=documents,
        )

    async def cache_lookup(self, project: Project, query: str, threshold: float) -> AgentToolResult:
        hit, query_vector = await self.nlp_controller.cache_lookup(
            project=project, query=query, threshold=threshold
        )
        # data carries the query embedding so the caller can reuse it for retrieval
        # on a miss (avoids a second embedding call).
        return AgentToolResult(
            name="cache_lookup",
            status="hit" if hit is not None else "miss",
            summary=(
                f"Cache hit (score={hit.score:.3f})"
                if hit is not None
                else "No semantically similar cached answer"
            ),
            data={"hit": hit, "query_vector": query_vector},
        )

    async def cache_store(
        self, project: Project, query: str, answer: str, sources: list
    ) -> AgentToolResult:
        stored = await self.nlp_controller.cache_store(
            project=project, query=query, answer=answer, sources=sources
        )
        return AgentToolResult(
            name="cache_store",
            status="success" if stored else "skipped",
            summary="Stored answer in cache" if stored else "Answer not cached",
            data=bool(stored),
        )

    async def rag_answer(
        self,
        project: Project,
        query: str,
        limit: int,
        history: list | None = None,
        documents: list | None = None,
    ) -> AgentToolResult:
        answer, _full_prompt, _chat_history = await self.nlp_controller.answer_rag_question(
            query=query,
            project=project,
            limit=limit,
            history=history,
            documents=documents,
        )
        if not answer:
            return AgentToolResult(
                name="rag_answer",
                status="empty",
                summary="No answer could be generated from project context",
                data=None,
            )
        return AgentToolResult(
            name="rag_answer",
            status="success",
            summary="Generated answer from project context",
            data=str(answer),
        )

    async def rag_answer_stream(
        self,
        project: Project,
        query: str,
        limit: int,
        history: list | None = None,
        documents: list | None = None,
    ):
        """Yield answer text chunks. Unlike rag_answer this cannot return an
        AgentToolResult; the caller builds the trace entry after the stream ends
        (status "success" if any chunk arrived, else "empty")."""
        async for chunk in self.nlp_controller.answer_rag_question_stream(
            query=query,
            project=project,
            limit=limit,
            history=history,
            documents=documents,
        ):
            yield chunk
