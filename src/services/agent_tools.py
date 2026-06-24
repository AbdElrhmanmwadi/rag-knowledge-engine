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

    async def rag_search(self, project: Project, query: str, limit: int) -> AgentToolResult:
        documents = await self.nlp_controller.search_in_vectordb(
            project=project,
            text=query,
            limit=limit,
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
        hit = await self.nlp_controller.cache_lookup(
            project=project, query=query, threshold=threshold
        )
        if hit is None:
            return AgentToolResult(
                name="cache_lookup",
                status="miss",
                summary="No semantically similar cached answer",
                data=None,
            )
        return AgentToolResult(
            name="cache_lookup",
            status="hit",
            summary=f"Cache hit (score={hit.score:.3f})",
            data=hit,
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

    async def rerank(self, query: str, documents: list, top_n: int) -> AgentToolResult:
        reordered = await self.nlp_controller.rerank_documents(
            query=query,
            documents=documents,
            top_n=top_n,
        )
        reordered = reordered or []
        return AgentToolResult(
            name="rerank",
            status="success",
            summary=f"Reranked {len(documents)} chunk(s) down to {len(reordered)}",
            data=reordered,
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
