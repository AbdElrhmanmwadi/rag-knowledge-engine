import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from services.agent_service import AgentService
from services.agent_tools import AgentToolResult


@dataclass
class FakeDocument:
    text: str
    score: float
    meta_data: dict | None = None


class FakeTools:
    def __init__(self, documents=None, answer=None):
        self.documents = documents or []
        self.answer = answer
        self.search_calls = 0
        self.answer_calls = 0

    async def rag_search(self, project, query, limit):
        self.search_calls += 1
        return AgentToolResult(
            name="rag_search",
            status="success",
            summary=f"Retrieved {len(self.documents)} document chunk(s)",
            data=self.documents,
        )

    async def rag_answer(self, project, query, limit):
        self.answer_calls += 1
        return AgentToolResult(
            name="rag_answer",
            status="success" if self.answer else "empty",
            summary="Generated answer from project context" if self.answer else "No answer",
            data=self.answer,
        )


class AgentServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_greeting_does_not_call_rag(self):
        tools = FakeTools()
        service = AgentService(tools=tools, default_limit=5)

        result = await service.run(project=object(), message="hello")

        self.assertIn("Ask me a question", result["answer"])
        self.assertEqual(tools.search_calls, 0)
        self.assertEqual(tools.answer_calls, 0)

    async def test_empty_retrieval_returns_safe_answer(self):
        tools = FakeTools(documents=[])
        service = AgentService(tools=tools, default_limit=5)

        result = await service.run(project=object(), message="What is in this project?")

        self.assertEqual(result["sources"], [])
        self.assertIn("could not find relevant", result["answer"])
        self.assertEqual(tools.search_calls, 1)
        self.assertEqual(tools.answer_calls, 0)

    async def test_sources_do_not_include_file_paths(self):
        document = FakeDocument(
            text="Project context",
            score=0.9,
            meta_data={
                "source": "report.pdf",
                "file_path": "C:/private/report.pdf",
                "path": "/private/report.pdf",
            },
        )
        tools = FakeTools(documents=[document], answer="The project says yes.")
        service = AgentService(tools=tools, default_limit=5)

        result = await service.run(project=object(), message="What does the report say?")

        self.assertEqual(result["answer"], "The project says yes.")
        self.assertEqual(result["sources"][0]["metadata"], {"source": "report.pdf"})
        self.assertEqual(tools.search_calls, 1)
        self.assertEqual(tools.answer_calls, 1)


if __name__ == "__main__":
    unittest.main()
