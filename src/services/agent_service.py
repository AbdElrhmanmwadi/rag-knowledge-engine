import re
import unicodedata
from typing import Any, TypedDict

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - exercised when langgraph is not installed
    END = None
    StateGraph = None

from helpers.observability import traceable
from models.db_schemes.minirag.scheme import Project
from services.agent_tools import AgentTools


# --- Intent classification (rule-based, multilingual: Arabic + English) ---

# Strip Arabic diacritics and tatweel so "مَرْحَبًا" and "مرحبا" match.
_AR_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def _normalize(text: str) -> str:
    """Lowercase, NFKC-fold, strip Arabic diacritics/punctuation and unify letters."""
    text = unicodedata.normalize("NFKC", text or "").strip().lower()
    text = _AR_DIACRITICS.sub("", text)
    text = text.translate(str.maketrans("أإآى", "اااي")).replace("ة", "ه")
    text = _NON_WORD.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


# Each set holds normalized smalltalk phrases. Order of lookup: greeting → thanks → farewell.
_GREETINGS = {
    "hi", "hello", "hey", "heya", "hiya", "yo", "howdy", "greetings", "good day",
    "good morning", "good afternoon", "good evening", "hi there", "hello there",
    "مرحبا", "مرحبتين", "اهلا", "اهلين", "اهلا وسهلا", "هلا", "هاي", "سلام",
    "السلام عليكم", "صباح الخير", "مساء الخير", "صباح النور", "مساء النور",
}
_THANKS = {
    "thanks", "thank you", "thanks a lot", "thank you so much", "thx", "ty",
    "appreciate it", "much appreciated", "cheers",
    "شكرا", "شكرا لك", "شكرا جزيلا", "مشكور", "تسلم", "ممنون", "يعطيك العافيه",
}
_FAREWELLS = {
    "bye", "goodbye", "good bye", "see you", "see you later", "cya", "good night",
    "take care",
    "باي", "وداعا", "مع السلامه", "الى اللقاء", "تصبح علي خير",
}
_SMALLTALK = {"greeting": _GREETINGS, "thanks": _THANKS, "farewell": _FAREWELLS}
# Vocabulary of individual smalltalk words for the short-message token check.
_SMALLTALK_VOCAB = {word for phrases in _SMALLTALK.values() for p in phrases for word in p.split()}


def classify_smalltalk(message: str) -> str | None:
    """Return 'greeting' | 'thanks' | 'farewell' for pure smalltalk, else None.

    Matches whole normalized phrases first, then falls back to a short-message check
    where every token is smalltalk vocabulary (catches "hi hi", "مرحبا اهلا").
    """
    normalized = _normalize(message)
    if not normalized:
        return "greeting"
    for kind, phrases in _SMALLTALK.items():
        if normalized in phrases:
            return kind
    tokens = normalized.split()
    if 1 <= len(tokens) <= 4 and all(token in _SMALLTALK_VOCAB for token in tokens):
        for kind, phrases in _SMALLTALK.items():
            if any(tokens[0] in p.split() for p in phrases):
                return kind
    return None


_ARABIC_CHARS = re.compile(r"[؀-ۿ]")


def detect_lang(text: str) -> str:
    """Coarse language detection: 'ar' if any Arabic letter is present, else 'en'."""
    return "ar" if _ARABIC_CHARS.search(text or "") else "en"


# Smalltalk replies keyed by language so an Arabic greeting gets an Arabic reply.
_SMALLTALK_REPLIES = {
    "en": {
        "greeting": "Hello! Ask me a question about this project and I will use its indexed knowledge to help.",
        "thanks": "You're welcome! Feel free to ask me anything else about this project.",
        "farewell": "Goodbye! Come back anytime you have questions about this project.",
    },
    "ar": {
        "greeting": "مرحباً! اسألني عن هذا المشروع وسأستخدم معرفته المفهرسة لمساعدتك.",
        "thanks": "على الرحب والسعة! لا تتردّد في سؤالي عن أي شيء آخر يخص المشروع.",
        "farewell": "إلى اللقاء! عُد متى شئت إن كان لديك أسئلة عن هذا المشروع.",
    },
}


class AgentState(TypedDict, total=False):
    project: Project
    message: str
    limit: int
    history: list[dict[str, str]]
    needs_rag: bool
    smalltalk_kind: str | None
    lang: str
    search_query: str
    # Declared as a graph channel so it survives between nodes under LangGraph;
    # an undeclared key returned by _retrieve would be dropped before _answer reads it.
    retrieved_documents: list[Any]
    answer: str
    sources: list[dict[str, Any]]
    tool_trace: list[dict[str, str]]
    # Answer-cache channels: cache_hit short-circuits retrieve/answer; only a
    # genuine generated answer (answer_cacheable) is written back to the cache.
    cache_hit: bool
    answer_cacheable: bool
    # Query embedding from cache lookup, reused for retrieval on a miss (no re-embed).
    query_vector: list[Any]


class AgentService:
    def __init__(
        self,
        tools: AgentTools,
        default_limit: int = 5,
        cache_enabled: bool = False,
        cache_threshold: float = 0.95,
    ):
        self.tools = tools
        self.default_limit = default_limit
        self.cache_enabled = cache_enabled
        self.cache_threshold = cache_threshold
        self.graph = self._build_graph()

    # Root span for the whole request: the traced steps below (condense_query,
    # search_in_vectordb, answer_rag_question, cohere/openai generate) nest under
    # it via contextvars instead of each becoming its own top-level trace.
    @traceable(run_type="chain", name="agent_run")
    async def run(
        self,
        project: Project,
        message: str,
        limit: int | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        state: AgentState = {
            "project": project,
            "message": message.strip(),
            "limit": limit or self.default_limit,
            "history": history or [],
            "tool_trace": [],
            "sources": [],
        }
        if self.graph is not None:
            result = await self.graph.ainvoke(state)
            return self._public_result(result)

        # Linear flow; each node self-guards (skips its work when not applicable),
        # so smalltalk, cache hits, and cache misses all share one straight path.
        state = await self._classify_intent(state)
        state = await self._cache_lookup(state)
        state = await self._retrieve(state)
        state = await self._answer(state)
        state = await self._cache_store(state)
        state = await self._finalize(state)
        return self._public_result(state)

    # Streaming bypasses the LangGraph graph on purpose: graph nodes exchange whole
    # states, which is exactly what token streaming is not. The node methods are
    # reused directly so both paths share classification/retrieval logic, and the
    # existing run() stays byte-for-byte identical for stream=false and eval_rag.py.
    @traceable(run_type="chain", name="agent_run_stream")
    async def run_stream(
        self,
        project: Project,
        message: str,
        limit: int | None = None,
        history: list[dict[str, str]] | None = None,
    ):
        """Yield event dicts: one "meta" (sources + trace so far), then "delta"
        events with text chunks, then one "final" with the completed tool trace."""
        state: AgentState = {
            "project": project,
            "message": message.strip(),
            "limit": limit or self.default_limit,
            "history": history or [],
            "tool_trace": [],
            "sources": [],
        }
        state = await self._classify_intent(state)
        # Answer cache: a hit returns the stored answer as a single delta, skipping
        # retrieval + generation entirely. On a miss the embedding is reused by _retrieve.
        state = await self._cache_lookup(state)
        if state.get("cache_hit"):
            state = await self._finalize(state)
            yield {
                "type": "meta",
                "sources": state.get("sources") or [],
                "tool_trace": list(state.get("tool_trace") or []),
            }
            yield {"type": "delta", "text": state["answer"]}
            yield {"type": "final", "tool_trace": state.get("tool_trace") or []}
            return

        if state["needs_rag"]:
            state = await self._retrieve(state)
        # Retrieval is done before generation starts, so the client can render
        # source citations while tokens are still arriving.
        yield {
            "type": "meta",
            "sources": state.get("sources") or [],
            "tool_trace": list(state.get("tool_trace") or []),
        }

        if not state.get("needs_rag") or not state.get("retrieved_documents"):
            # Smalltalk and the no-context fallback are single-shot answers;
            # reuse the non-stream node so the wording stays identical.
            state = await self._answer(state)
            state = await self._finalize(state)
            yield {"type": "delta", "text": state["answer"]}
            yield {"type": "final", "tool_trace": state.get("tool_trace") or []}
            return

        got_chunks = False
        answer_parts: list[str] = []
        async for chunk in self.tools.rag_answer_stream(
            project=state["project"],
            query=state.get("search_query") or state["message"],
            limit=state["limit"],
            history=state.get("history"),
            # Reuse the chunks already fetched by _retrieve instead of searching again.
            documents=state.get("retrieved_documents"),
        ):
            if chunk:
                got_chunks = True
                answer_parts.append(chunk)
                yield {"type": "delta", "text": chunk}

        if got_chunks:
            trace = {
                "name": "rag_answer",
                "status": "success",
                "summary": "Generated answer from project context",
            }
            # Cache the fully streamed answer so future similar questions hit the cache.
            state["answer"] = "".join(answer_parts)
            state["answer_cacheable"] = True
            state = await self._cache_store(state)
        else:
            trace = {
                "name": "rag_answer",
                "status": "empty",
                "summary": "No answer could be generated from project context",
            }
            # Same fallback sentence as the non-stream path.
            yield {"type": "delta", "text": "I could not generate an answer from the retrieved project context."}
        state.setdefault("tool_trace", []).append(trace)
        yield {"type": "final", "tool_trace": state["tool_trace"]}

    def _build_graph(self):
        if StateGraph is None:
            return None
        graph = StateGraph(AgentState)
        graph.add_node("classify_intent", self._classify_intent)
        graph.add_node("cache_lookup", self._cache_lookup)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("answer", self._answer)
        graph.add_node("cache_store", self._cache_store)
        graph.add_node("finalize", self._finalize)
        graph.set_entry_point("classify_intent")
        graph.add_edge("classify_intent", "cache_lookup")
        graph.add_edge("cache_lookup", "retrieve")
        graph.add_edge("retrieve", "answer")
        graph.add_edge("answer", "cache_store")
        graph.add_edge("cache_store", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    async def _classify_intent(self, state: AgentState) -> AgentState:
        kind = classify_smalltalk(state["message"])
        state["smalltalk_kind"] = kind
        state["lang"] = detect_lang(state["message"])
        state["needs_rag"] = kind is None
        state.setdefault("tool_trace", []).append(
            {
                "name": "classify_intent",
                "status": "success",
                "summary": "RAG required" if state["needs_rag"] else f"Smalltalk: {kind}",
            }
        )
        return state

    async def _cache_lookup(self, state: AgentState) -> AgentState:
        # Only RAG questions are cacheable; smalltalk is answered directly.
        if not self.cache_enabled or not state.get("needs_rag"):
            return state
        result = await self.tools.cache_lookup(
            project=state["project"],
            query=state["message"],
            threshold=self.cache_threshold,
        )
        state.setdefault("tool_trace", []).append(self._trace(result))
        data = result.data or {}
        # Keep the embedding so _retrieve can reuse it on a miss.
        state["query_vector"] = data.get("query_vector")
        cached = data.get("hit")
        if result.status == "hit" and cached is not None:
            metadata = cached.meta_data or {}
            state["answer"] = metadata.get("answer") or ""
            state["sources"] = metadata.get("sources") or []
            state["cache_hit"] = True
        return state

    async def _retrieve(self, state: AgentState) -> AgentState:
        # Skip retrieval for smalltalk and for answered-from-cache turns.
        if not state.get("needs_rag") or state.get("cache_hit"):
            return state
        query = state["message"]
        if state.get("history"):
            rewrite = await self.tools.rewrite_query(query=query, history=state["history"])
            state.setdefault("tool_trace", []).append(self._trace(rewrite))
            query = rewrite.data or query
        state["search_query"] = query
        # Reuse the embedding from cache lookup only when the query was NOT rewritten
        # (a rewritten follow-up is a different string, so its embedding differs).
        reuse_vector = state.get("query_vector") if query == state["message"] else None
        # Reranking (when enabled) runs inside search_in_vectordb: it fetches a wider
        # candidate pool and trims back to `limit`, so there is no extra rerank here.
        result = await self.tools.rag_search(
            project=state["project"],
            query=query,
            limit=state["limit"],
            query_vector=reuse_vector,
        )
        documents = result.data or []
        state.setdefault("tool_trace", []).append(self._trace(result))

        state["retrieved_documents"] = documents
        state["sources"] = self._format_sources(state["retrieved_documents"])
        return state

    async def _answer(self, state: AgentState) -> AgentState:
        # Answer already resolved from cache — nothing to generate.
        if state.get("cache_hit"):
            return state

        if not state.get("needs_rag"):
            replies = _SMALLTALK_REPLIES.get(state.get("lang"), _SMALLTALK_REPLIES["en"])
            state["answer"] = replies.get(state.get("smalltalk_kind"), replies["greeting"])
            return state

        if not state.get("retrieved_documents"):
            state["answer"] = "I could not find relevant indexed project context for that question."
            return state

        result = await self.tools.rag_answer(
            project=state["project"],
            query=state.get("search_query") or state["message"],
            limit=state["limit"],
            history=state.get("history"),
            # Reuse the chunks already fetched by _retrieve instead of searching again.
            documents=state.get("retrieved_documents"),
        )
        state.setdefault("tool_trace", []).append(self._trace(result))
        state["answer"] = result.data or "I could not generate an answer from the retrieved project context."
        # Only a genuinely generated answer is worth caching.
        state["answer_cacheable"] = result.status == "success" and bool(result.data)
        return state

    async def _cache_store(self, state: AgentState) -> AgentState:
        # Cache only fresh, genuine RAG answers (not smalltalk, cache hits, or fallbacks).
        if (
            not self.cache_enabled
            or not state.get("needs_rag")
            or state.get("cache_hit")
            or not state.get("answer_cacheable")
        ):
            return state
        result = await self.tools.cache_store(
            project=state["project"],
            # Key on the raw message so store and lookup (which uses the raw message
            # too) stay consistent — otherwise a rewritten query is stored but never found.
            query=state["message"],
            answer=state.get("answer") or "",
            sources=state.get("sources") or [],
        )
        state.setdefault("tool_trace", []).append(self._trace(result))
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
            "cache_hit": bool(state.get("cache_hit")),
        }
