# Prompt: Answer feedback (👍/👎) — frontend integration

> Copy everything below this line and give it to the frontend developer / AI agent.

---

The backend now records user feedback on answers and exposes analytics. Two endpoints,
both requiring `Authorization: Bearer <token>` and access to the project
(the current user must own `project_id`, otherwise `404`/`403`):

- `POST /api/v1/feedback/{project_id}` — submit one 👍/👎 rating on an answer
- `GET  /api/v1/feedback/{project_id}/analytics` — aggregate stats (for an admin view)

## 1. Submit feedback — `POST /api/v1/feedback/{project_id}`

Send this **after** an answer is shown, when the user clicks 👍 or 👎.

Request body (`application/json`):

```json
{
  "question": "how much is the Galaxy plan?",   // the user's question text
  "answer":   "The Galaxy plan costs 19 USD.",   // the answer text that was shown
  "rating":   1,                                  // 1 = 👍 helpful, -1 = 👎 not helpful
  "session_id": 42,                               // optional: the agent session id, if any
  "comment": "wrong price"                        // optional: free text (nice to ask on 👎)
}
```

Success `200`:

```json
{ "signal": "feedback_success", "feedback_id": 123 }
```

Errors:

| status | signal | meaning |
|---|---|---|
| `400` | `feedback_invalid_rating` | `rating` was not `1` or `-1` |
| `401` | — | missing/invalid token |
| `404` | — | project not found / not owned by the user |

Rules:
- `rating` **must** be exactly `1` or `-1` (no `0`, no other values).
- `question` and `answer` are required; send the exact texts that were displayed.
- `session_id` and `comment` are optional (`null`/omit when unused). Use `session_id`
  when the answer came from the agent chat (`/api/v1/agent/chat`); omit it for a direct
  RAG answer (`/api/v1/nlp/index/answer`).

### Example (fetch)

```js
async function sendFeedback(projectId, { question, answer, rating, sessionId, comment }) {
  const res = await fetch(`/api/v1/feedback/${projectId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      question,
      answer,
      rating,                       // 1 or -1
      session_id: sessionId ?? null,
      comment: comment ?? null,
    }),
  });
  if (!res.ok) throw new Error(`feedback failed: ${res.status}`);
  return res.json();               // { signal, feedback_id }
}
```

### UX guidance

- Render a 👍 and a 👎 button under **each assistant answer**.
- One rating per answer: after the user picks one, highlight it and disable both
  (or allow switching by sending the new rating — each call inserts a new row).
- On 👎, optionally open a small comment box and include it as `comment`.
- Keep the buttons optimistic: show the selected state immediately, and only revert
  if the request fails.

## 2. Analytics — `GET /api/v1/feedback/{project_id}/analytics`

For an admin/dashboard screen. Optional query param `top_n` (default `10`, max `50`)
controls how many disliked questions are returned.

Success `200`:

```json
{
  "signal": "feedback_analytics_success",
  "total": 128,
  "positive": 96,
  "negative": 32,
  "csat": 0.75,                        // positive / total, or null if total = 0
  "top_disliked_questions": [
    { "question": "refund policy?", "count": 9 },
    { "question": "how to cancel?", "count": 4 }
  ]
}
```

Use it to show: total feedback, a CSAT gauge (`csat * 100`%), a 👍/👎 split, and a list
of the most-disliked questions (these are your knowledge-base gaps to fix).

> There is also a ready-made Grafana dashboard for this at
> `http://localhost/grafana/d/feedback-analytics` — the API above is for building it into
> the app's own admin UI.

## Notes

- Both endpoints need the bearer token; unauthenticated calls return `401`.
- Feedback is stored per project; analytics are scoped to the `project_id` in the path.
- Nothing else in the answer/chat flow changes — this is additive.
