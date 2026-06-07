from typing import Any, TypedDict

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - exercised when langgraph is not installed
    END = None
    StateGraph = None

from models.db_schemes.minirag.scheme import Project
from services.agent_tools import AgentTools


class AgentState(TypedDict, total=False):
    project: Project
    message: str
    limit: int
    needs_rag: bool
    answer: str
    sources: list[dict[str, Any]]
    tool_trace: list[dict[str, str]]


class AgentService:
    def __init__(self, tools: AgentTools, default_limit: int = 5):
        self.tools = tools
        self.default_limit = default_limit
        self.graph = self._build_graph()

    async def run(self, project: Project, message: str, limit: int | None = None) -> dict[str, Any]:
        state: AgentState = {
            "project": project,
            "message": message.strip(),
            "limit": limit or self.default_limit,
            "tool_trace": [],
            "sources": [],
        }
        if self.graph is not None:
            result = await self.graph.ainvoke(state)
            return self._public_result(result)

        state = await self._classify_intent(state)
        if state["needs_rag"]:
            state = await self._retrieve(state)
        state = await self._answer(state)
        state = await self._finalize(state)
        return self._public_result(state)

    def _build_graph(self):
        if StateGraph is None:
            return None
        graph = StateGraph(AgentState)
        graph.add_node("classify_intent", self._classify_intent)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("answer", self._answer)
        graph.add_node("finalize", self._finalize)
        graph.set_entry_point("classify_intent")
        graph.add_conditional_edges(
            "classify_intent",
            lambda state: "retrieve" if state.get("needs_rag") else "answer",
            {"retrieve": "retrieve", "answer": "answer"},
        )
        graph.add_edge("retrieve", "answer")
        graph.add_edge("answer", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    async def _classify_intent(self, state: AgentState) -> AgentState:
        message = state["message"].strip().lower()
        conversational = {
            "hi",
            "hello",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
        }
        state["needs_rag"] = message not in conversational
        state.setdefault("tool_trace", []).append(
            {
                "name": "classify_intent",
                "status": "success",
                "summary": "RAG required" if state["needs_rag"] else "Answered without retrieval",
            }
        )
        return state

    async def _retrieve(self, state: AgentState) -> AgentState:
        result = await self.tools.rag_search(
            project=state["project"],
            query=state["message"],
            limit=state["limit"],
        )
        state["retrieved_documents"] = result.data or []
        state["sources"] = self._format_sources(state["retrieved_documents"])
        state.setdefault("tool_trace", []).append(self._trace(result))
        return state

    async def _answer(self, state: AgentState) -> AgentState:
        if not state.get("needs_rag"):
            state["answer"] = "Hello. Ask me a question about this project and I will use its indexed knowledge to help."
            return state

        if not state.get("retrieved_documents"):
            state["answer"] = "I could not find relevant indexed project context for that question."
            return state

        result = await self.tools.rag_answer(
            project=state["project"],
            query=state["message"],
            limit=state["limit"],
        )
        state.setdefault("tool_trace", []).append(self._trace(result))
        state["answer"] = result.data or "I could not generate an answer from the retrieved project context."
        return state

    async def _finalize(self, state: AgentState) -> AgentState:
        state["answer"] = str(state.get("answer") or "").strip()
        return state

    def _format_sources(self, documents) -> list[dict[str, Any]]:
        sources = []
        for document in documents or []:
            metadata = dict(document.meta_data or {})
            metadata.pop("file_path", None)
            metadata.pop("path", None)
            sources.append(
                {
                    "text": document.text,
                    "score": document.score,
                    "metadata": metadata,
                }
            )
        return sources

    def _trace(self, result) -> dict[str, str]:
        return {
            "name": result.name,
            "status": result.status,
            "summary": result.summary,
        }

    def _public_result(self, state: AgentState) -> dict[str, Any]:
        return {
            "answer": state.get("answer") or "",
            "sources": state.get("sources") or [],
            "tool_trace": state.get("tool_trace") or [],
        }
