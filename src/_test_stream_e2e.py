"""Throwaway E2E test for SSE streaming against the running server."""
import json
import sys

import requests

BASE = "http://localhost:8000"
PROJECT = 1000
USER_ID = 1  # wadiabood577@gmail.com - password changed by today's reset test, so mint a token directly


def parse_sse(resp):
    events = []
    buffer = ""
    for raw in resp.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        if raw == "":
            if buffer:
                lines = buffer.split("\n")
                event = next((l[7:] for l in lines if l.startswith("event: ")), None)
                data = next((l[6:] for l in lines if l.startswith("data: ")), None)
                events.append((event, json.loads(data) if data else None))
                buffer = ""
        else:
            buffer = buffer + "\n" + raw if buffer else raw
    return events


def main():
    from helpers.config import get_settings
    from helpers.jwt import create_access_token

    token = create_access_token(user_id=USER_ID, settings=get_settings())
    headers = {"Authorization": f"Bearer {token}"}

    # 1. smalltalk stream (rule-based, no LLM call)
    r = requests.post(
        f"{BASE}/api/v1/agent/chat/{PROJECT}",
        headers=headers,
        json={"message": "مرحبا", "stream": True},  # "مرحبا" as escapes: immune to encoding mangling
        stream=True,
        timeout=120,
    )
    ct = r.headers.get("content-type", "")
    print(f"[smalltalk] status={r.status_code} content-type={ct}")
    if "text/event-stream" not in ct:
        print("SERVER IS RUNNING OLD CODE (got JSON, not SSE):", r.text[:200])
        sys.exit(1)
    events = parse_sse(r)
    names = [e[0] for e in events]
    print(f"[smalltalk] events={names}")
    assert names == ["meta", "delta", "done"], names
    session_id = events[0][1]["session_id"]
    assert "مرحباً" in events[1][1]["text"]  # "مرحباً"
    assert events[-1][1].get("signal"), events[-1]
    print(f"[smalltalk] OK  session_id={session_id}")

    # 2. real RAG question, streamed
    r = requests.post(
        f"{BASE}/api/v1/agent/chat/{PROJECT}",
        headers=headers,
        json={"message": "Does Numero own cellular networks?", "stream": True, "session_id": session_id},
        stream=True,
        timeout=180,
    )
    print(f"[rag] status={r.status_code} content-type={r.headers.get('content-type','')}")
    events = parse_sse(r)
    names = [e[0] for e in events]
    deltas = [e[1]["text"] for e in events if e[0] == "delta"]
    meta = next((e[1] for e in events if e[0] == "meta"), {})
    done = next((e[1] for e in events if e[0] == "done"), {})
    print(f"[rag] meta sources={len(meta.get('sources', []))} trace={[t['name'] for t in meta.get('tool_trace', [])]}")
    print(f"[rag] delta count={len(deltas)}")
    assert names[0] == "meta" and names[-1] == "done", names
    concat = "".join(deltas)
    assert concat.strip() == done.get("answer", "").strip(), "concatenated deltas != done.answer"
    print(f"[rag] answer ({len(done['answer'])} chars): {done['answer'][:160]}...")
    if len(deltas) > 1:
        print("[rag] OK - true incremental streaming (multiple deltas)")
    else:
        print("[rag] WARNING - only one delta (stream worked but arrived as a single chunk)")

    # 3. session history: exactly one assistant message per question, full text
    r = requests.get(f"{BASE}/api/v1/agent/sessions/{PROJECT}/{session_id}", headers=headers, timeout=30)
    r.raise_for_status()
    messages = r.json()["session"]["messages"]
    roles = [m["role"] for m in messages]
    print(f"[persist] roles={roles}")
    assert roles == ["user", "assistant", "user", "assistant"], roles
    assert messages[-1]["content"].strip() == done["answer"].strip()
    assert "sources" in (messages[-1]["metadata"] or {})
    print("[persist] OK - one assistant message, full text, sources metadata present")

    # 4. stream=false regression
    r = requests.post(
        f"{BASE}/api/v1/agent/chat/{PROJECT}",
        headers=headers,
        json={"message": "hi", "stream": False},
        timeout=60,
    )
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["signal"] == "agent_chat_success" and body["answer"], body
    print(f"[non-stream] OK - JSON unchanged: {list(body.keys())}")

    print("ALL E2E TESTS PASSED")


if __name__ == "__main__":
    main()
