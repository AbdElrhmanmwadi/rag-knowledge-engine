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

    async def rag_answer(self, project: Project, query: str, limit: int) -> AgentToolResult:
        answer, _full_prompt, _chat_history = await self.nlp_controller.answer_rag_question(
            query=query,
            project=project,
            limit=limit,
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
