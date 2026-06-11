"""Throwaway smoke test for the streaming path (no DB / no LLM API)."""
import asyncio

import controllers  # noqa: F401  (imported first like the app does, avoids a pre-existing services<->controllers cycle)
from helpers.streaming import aiter_in_thread, sse, open_stream_with_retry, is_rate_limit_error
from helpers.observability import reduce_stream_chunks
from services.agent_service import AgentService


def test_helpers():
    # sse formatting
    block = sse("delta", {"text": "مرحبا"})
    assert block == 'event: delta\ndata: {"text": "مرحبا"}\n\n', block

    # reduce_fn folds chunks + usage
    out = reduce_stream_chunks([{"text": "a"}, {"text": "b"}, {"usage_metadata": {"total_tokens": 5}}])
    assert out == {"text": "ab", "usage_metadata": {"total_tokens": 5}}, out

    # retry helper: 429 twice then success
    calls = {"n": 0}
    class RL(Exception):
        status_code = 429
    def open_fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RL()
        return iter(["x", "y"])
    stream = open_stream_with_retry(open_fn, max_attempts=3, base_delay=0.01)
    assert list(stream) == ["x", "y"]
    assert calls["n"] == 3
    assert is_rate_limit_error(RL())

    # non-retryable propagates
    def open_boom():
        raise ValueError("boom")
    try:
        open_stream_with_retry(open_boom, base_delay=0.01)
        raise AssertionError("should have raised")
    except ValueError:
        pass
    print("helpers OK")


def test_aiter_in_thread():
    def gen():
        yield from ["one", "two", "three"]
    async def run():
        return [c async for c in aiter_in_thread(gen())]
    assert asyncio.run(run()) == ["one", "two", "three"]
    print("aiter_in_thread OK")


class FakeDoc:
    def __init__(self, text):
        self.text = text
        self.score = 0.9
        self.meta_data = {"page": 1}


class FakeTools:
    async def rewrite_query(self, query, history):
        from services.agent_tools import AgentToolResult
        return AgentToolResult(name="rewrite_query", status="success", summary="Query already standalone", data=query)

    async def rag_search(self, project, query, limit):
        from services.agent_tools import AgentToolResult
        docs = [FakeDoc("chunk-a"), FakeDoc("chunk-b")] if "found" in query else []
        return AgentToolResult(name="rag_search", status="success", summary=f"Retrieved {len(docs)} document chunk(s)", data=docs)

    async def rag_answer(self, **kwargs):
        from services.agent_tools import AgentToolResult
        return AgentToolResult(name="rag_answer", status="success", summary="Generated answer from project context", data="full answer")

    async def rag_answer_stream(self, project, query, limit, history=None, documents=None):
        for chunk in ["Hello ", "streamed ", "world"]:
            yield chunk


class EmptyStreamTools(FakeTools):
    async def rag_answer_stream(self, project, query, limit, history=None, documents=None):
        return
        yield  # makes this an async generator that yields nothing


def collect(service, message):
    async def run():
        return [e async for e in service.run_stream(project=object(), message=message)]
    return asyncio.run(run())


def test_run_stream():
    service = AgentService(tools=FakeTools(), default_limit=5)

    # 1. smalltalk: meta -> one delta -> final
    events = collect(service, "مرحبا")
    types = [e["type"] for e in events]
    assert types == ["meta", "delta", "final"], types
    assert "مرحباً" in events[1]["text"], events[1]
    assert events[0]["sources"] == []

    # 2. rag question with documents: meta (sources ready) -> 3 deltas -> final with rag_answer trace
    events = collect(service, "what is found in the docs?")
    types = [e["type"] for e in events]
    assert types == ["meta", "delta", "delta", "delta", "final"], types
    assert len(events[0]["sources"]) == 2, events[0]
    answer = "".join(e["text"] for e in events if e["type"] == "delta")
    assert answer == "Hello streamed world", answer
    trace_names = [t["name"] for t in events[-1]["tool_trace"]]
    assert trace_names == ["classify_intent", "rag_search", "rag_answer"], trace_names
    assert events[-1]["tool_trace"][-1]["status"] == "success"

    # 3. no documents retrieved -> fallback sentence as one delta
    events = collect(service, "question with no matches")
    deltas = [e for e in events if e["type"] == "delta"]
    assert len(deltas) == 1 and "could not find relevant" in deltas[0]["text"], deltas

    # 4. documents found but stream yields nothing -> empty trace + fallback delta
    service_empty = AgentService(tools=EmptyStreamTools(), default_limit=5)
    events = collect(service_empty, "what is found here?")
    deltas = [e for e in events if e["type"] == "delta"]
    assert len(deltas) == 1 and "could not generate an answer" in deltas[0]["text"], deltas
    assert events[-1]["tool_trace"][-1]["status"] == "empty"

    print("run_stream OK")


def test_run_unchanged():
    # stream=false regression: run() must still produce the same shape
    service = AgentService(tools=FakeTools(), default_limit=5)
    async def run():
        return await service.run(project=object(), message="what is found in the docs?")
    result = asyncio.run(run())
    assert result["answer"] == "full answer", result
    assert len(result["sources"]) == 2
    print("run() unchanged OK")


if __name__ == "__main__":
    test_helpers()
    test_aiter_in_thread()
    test_run_stream()
    test_run_unchanged()
    print("ALL SMOKE TESTS PASSED")
