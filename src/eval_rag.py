"""RAG evaluation harness — LangSmith dataset + Cohere LLM-as-judge.

What it does
------------
1. Parses the gold Q&A from ``knowledge_base_qa.txt`` into (question, reference)
   pairs and pushes them to a LangSmith dataset (created once, reused after).
2. Runs the deployed agent against each question through the HTTP API
   (login -> /api/v1/agent/chat/{project}), exactly like ``_try_kb.py``.
3. Scores every answer with a Cohere judge on two dimensions:
     - correctness:  does the agent's answer match the reference answer?
     - faithfulness: is the answer grounded in the retrieved sources
                     (i.e. no hallucination / no made-up facts)?
   Both scores + the judge's reasoning land in the LangSmith experiment so you
   can open the dashboard and read every wrong answer with its explanation.

Why a judge instead of word overlap: word overlap (the old ``ovl`` metric)
rewards shared tokens, not meaning. A correct answer phrased differently scores
low; a wrong answer that reuses words scores high. An LLM judge compares meaning.

Usage (from the ``src/`` dir, with ``.env`` in place and the API server running):
    python eval_rag.py --limit 30
    python eval_rag.py                 # all parsed Q&A
    python eval_rag.py --dry-run       # parse + judge nothing, just show counts

Cohere trial accounts are rate-limited (~20 calls/min). The judge retries on
429 with backoff and the run is single-threaded, so it is slow but safe; raise
``--sleep`` if you still hit limits.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

from helpers.config import get_settings
from helpers.observability import configure_langsmith

sys.stdout.reconfigure(encoding="utf-8")

# --- defaults (override on the CLI) ------------------------------------------
BASE = "http://localhost:8000"
EMAIL = "wadiabood577@gmail.com"
PASSWORD = "Ab0230@wadi"
PROJECT = 1000  # projects with the Numero eSIM KB ingested: 668, 700, 1000 (NOT 600)
KB_PATH = Path(__file__).with_name("knowledge_base_qa.txt")
DATASET_NAME = "numero-esim-kb"

JUDGE_PROMPT = """You are a strict evaluator for a customer-service RAG assistant.

You are given a user QUESTION, the assistant's ANSWER, the reference (gold) \
ANSWER from the knowledge base, and the SOURCES the assistant retrieved.

Score two things, each from 0.0 to 1.0:
- "correctness": how well the assistant's answer matches the reference answer in \
meaning. 1.0 = fully correct and complete; 0.5 = partially correct or missing \
key info; 0.0 = wrong or contradicts the reference.
- "faithfulness": is every claim in the assistant's answer supported by the \
SOURCES? 1.0 = fully grounded; 0.0 = contains claims not in the sources \
(hallucination). If there are no sources, judge against the reference answer.

Return ONLY a JSON object, no prose, no markdown fences:
{{"correctness": <float>, "faithfulness": <float>, "reason": "<one sentence>"}}

QUESTION:
{question}

REFERENCE ANSWER:
{reference}

ASSISTANT ANSWER:
{answer}

SOURCES:
{sources}
"""


# --- KB parsing --------------------------------------------------------------
def parse_kb(path: Path) -> list[dict]:
    """Return [{question, reference}] from the markdown export.

    Every ``### heading`` is a question; the text until the next ``#`` heading is
    its answer. The ``## Contents`` section has no ``###`` headings, so it is
    skipped naturally.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    qa: list[dict] = []
    question: str | None = None
    answer: list[str] = []

    def flush() -> None:
        if question:
            body = "\n".join(answer).strip()
            if body:
                qa.append({"question": question, "reference": body})

    for line in lines:
        if line.startswith("### "):
            flush()
            question = line[4:].strip()
            answer = []
        elif line.startswith("#"):  # any other heading ends the current answer
            flush()
            question = None
            answer = []
        elif question is not None:
            answer.append(line)
    flush()
    return qa


# --- agent (the system under test) -------------------------------------------
class Agent:
    def __init__(self, base: str, email: str, password: str, project: int):
        self.base = base
        self.project = project
        r = requests.post(
            f"{base}/auth/login", json={"email": email, "password": password}, timeout=30
        )
        r.raise_for_status()
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def ask(self, question: str, retries: int = 3) -> dict:
        url = f"{self.base}/api/v1/agent/chat/{self.project}"
        last = ""
        for attempt in range(retries):
            r = requests.post(url, headers=self.headers, json={"message": question}, timeout=120)
            if r.status_code == 200:
                data = r.json()
                if data.get("answer"):
                    return {"answer": data["answer"], "sources": data.get("sources", [])}
                last = "empty answer"
            else:
                last = f"HTTP {r.status_code}: {r.text[:150]}"
            time.sleep(4 * (attempt + 1))  # back off (covers Cohere rate limits)
        return {"answer": "", "sources": [], "error": last}


# --- Cohere judge ------------------------------------------------------------
def make_judge(settings, sleep: float):
    import cohere

    client = cohere.Client(api_key=settings.COHERE_API_KEY)
    model = settings.GENERATION_MODEL_ID

    def judge(question: str, answer: str, reference: str, sources: list) -> dict:
        src_text = "\n".join(
            f"- {s.get('text', '')[:400]}" for s in sources[:5]
        ) or "(no sources retrieved)"
        prompt = JUDGE_PROMPT.format(
            question=question, reference=reference, answer=answer, sources=src_text
        )
        for attempt in range(5):
            try:
                resp = client.chat(model=model, message=prompt, temperature=0.0, max_tokens=300)
                raw = (resp.text or "").strip()
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                data = json.loads(match.group(0) if match else raw)
                time.sleep(sleep)
                return {
                    "correctness": float(data.get("correctness", 0.0)),
                    "faithfulness": float(data.get("faithfulness", 0.0)),
                    "reason": str(data.get("reason", ""))[:300],
                }
            except Exception as exc:  # rate limit, parse error, etc.
                wait = sleep + 5 * (attempt + 1)
                print(f"    judge retry {attempt + 1}/5 in {wait:.0f}s ({exc})")
                time.sleep(wait)
        return {"correctness": 0.0, "faithfulness": 0.0, "reason": "judge failed"}

    return judge


# --- main --------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="max Q&A to evaluate (0 = all)")
    ap.add_argument("--project", type=int, default=PROJECT)
    ap.add_argument("--email", default=EMAIL)
    ap.add_argument("--password", default=PASSWORD)
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--dataset", default=DATASET_NAME)
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds to pace judge calls")
    ap.add_argument("--dry-run", action="store_true", help="parse only, no API/judge calls")
    args = ap.parse_args()

    qa = parse_kb(KB_PATH)
    if args.limit:
        qa = qa[: args.limit]
    print(f"Parsed {len(qa)} Q&A pairs from {KB_PATH.name}")
    if args.dry_run:
        for i, item in enumerate(qa[:3], 1):
            print(f"\n[{i}] Q: {item['question']}\n    REF: {item['reference'][:120]}...")
        return

    settings = get_settings()
    if not configure_langsmith(settings):
        sys.exit("LangSmith not active. Set LANGSMITH_TRACING=true and LANGSMITH_API_KEY in .env")

    from langsmith import Client
    from langsmith.evaluation import evaluate

    client = Client()

    # 1) build/refresh the dataset
    if client.has_dataset(dataset_name=args.dataset):
        dataset = client.read_dataset(dataset_name=args.dataset)
    else:
        dataset = client.create_dataset(
            dataset_name=args.dataset, description="Numero eSIM gold Q&A from knowledge_base_qa.txt"
        )
        client.create_examples(
            inputs=[{"question": x["question"]} for x in qa],
            outputs=[{"reference": x["reference"]} for x in qa],
            dataset_id=dataset.id,
        )
        print(f"Created dataset '{args.dataset}' with {len(qa)} examples")

    # 2) system under test
    agent = Agent(args.base, args.email, args.password, args.project)

    def target(inputs: dict) -> dict:
        return agent.ask(inputs["question"])

    # 3) judge -> two LangSmith feedback scores
    judge = make_judge(settings, args.sleep)

    def correctness_and_faithfulness(run, example) -> dict:
        out = run.outputs or {}
        verdict = judge(
            question=example.inputs["question"],
            answer=out.get("answer", ""),
            reference=example.outputs["reference"],
            sources=out.get("sources", []),
        )
        return {
            "results": [
                {"key": "correctness", "score": verdict["correctness"], "comment": verdict["reason"]},
                {"key": "faithfulness", "score": verdict["faithfulness"], "comment": verdict["reason"]},
            ]
        }

    # 4) run — single-threaded to respect the Cohere trial rate limit
    results = evaluate(
        target,
        data=args.dataset,
        evaluators=[correctness_and_faithfulness],
        experiment_prefix="rag-eval",
        max_concurrency=1,
    )

    # 5) local summary (full detail + reasons live in the LangSmith dashboard)
    rows = list(results)
    n = len(rows)
    correct = faithful = 0.0
    for row in rows:
        for res in row["evaluation_results"]["results"]:
            if res.key == "correctness":
                correct += res.score or 0.0
            elif res.key == "faithfulness":
                faithful += res.score or 0.0
    if n:
        print(f"\n==== {n} questions evaluated ====")
        print(f"avg correctness : {correct / n:.2f}")
        print(f"avg faithfulness: {faithful / n:.2f}")
    print(f"\nOpen LangSmith -> project '{settings.LANGSMITH_PROJECT}', experiment 'rag-eval...' "
          "to read each answer, its scores, and the judge's reasoning.")


if __name__ == "__main__":
    main()
