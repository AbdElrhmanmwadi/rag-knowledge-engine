# RAG Knowledge Engine - Architecture & Data Models

## System Architecture

### Application Stack
```
┌───────────────────────────────────────────────────────────────┐
│              FastAPI Application (uvicorn :8000)                │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Routes Layer                                              │ │
│  │  ├─ base_router        (/api/v1)                          │ │
│  │  ├─ auth_router        (/auth)                            │ │
│  │  ├─ data_router        (/api/v1/data)                     │ │
│  │  ├─ nlp_router         (/api/v1/nlp)                      │ │
│  │  ├─ agent_router       (/api/v1/agent)   ← chat + SSE     │ │
│  │  ├─ translation_router (/translate)                       │ │
│  │  └─ voice_router       (/api/v1/voice)                    │ │
│  └──────────────────────────────────────────────────────────┘ │
│                        ↓                                       │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Controllers Layer (Business Logic)                        │ │
│  │  AuthController · DataController · ProcessController        │ │
│  │  NLPController · ProjectController · AgentController        │ │
│  │  TranslationController · VoiceController · BaseController   │ │
│  └──────────────────────────────────────────────────────────┘ │
│                        ↓                                       │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Services Layer                                            │ │
│  │  ├─ agent_service  (LangGraph nodes: classify→retrieve→    │ │
│  │  │                  answer→finalize; + run_stream for SSE) │ │
│  │  ├─ agent_tools    (rewrite_query, rag_search, rag_answer) │ │
│  │  └─ project_access (per-user project/job authorization)    │ │
│  └──────────────────────────────────────────────────────────┘ │
│            ↙                  ↓                   ↖             │
│  ┌──────────────┐  ┌────────────────────┐  ┌────────────────┐ │
│  │ Models Layer │  │   Stores Layer     │  │  Helpers Layer │ │
│  │              │  │                    │  │                │ │
│  │ Project      │  │ LLM Providers      │  │ config.py      │ │
│  │ Asset        │  │  - Cohere/OpenAI   │  │ jwt.py         │ │
│  │ DataChunk    │  │ Embedding (same)   │  │ security.py    │ │
│  │ User         │  │ VectorDB           │  │ email.py       │ │
│  │ RefreshToken │  │  - PGVector (def.) │  │ google_auth.py │ │
│  │ AgentSession │  │  - Qdrant          │  │ auth_deps.py   │ │
│  │ AgentMessage │  │ Voice (Whisper/    │  │ observability  │ │
│  │ TranslationJob│ │   Piper)           │  │ streaming.py   │ │
│  │              │  │ Translation        │  │                │ │
│  │              │  │  - LibreTranslate  │  │                │ │
│  └──────────────┘  └────────────────────┘  └────────────────┘ │
└───────────────────────────────────────────────────────────────┘
              ↓                          ↓                  ↓
    ┌──────────────────────┐  ┌──────────────────┐  ┌──────────────┐
    │  PostgreSQL          │  │  Vector store    │  │ LibreTranslate│
    │  + pgvector          │  │  (PGVector in    │  │  (Docker,     │
    │                      │  │   the same PG, or│  │   ar+en)      │
    │  Tables:             │  │   Qdrant on disk)│  │               │
    │  projects, assets,   │  │  collection_N    │  │ Whisper/Piper │
    │  chunks, users,      │  │  vectors+payload │  │  run in-proc  │
    │  refresh_tokens,     │  │  384-dim         │  │  (subprocess) │
    │  agent_sessions,     │  │  distance: DOT/  │  └──────────────┘
    │  agent_messages,     │  │  cosine          │
    │  translation_jobs    │  └──────────────────┘
    └──────────────────────┘
```

> Note: `docker/docker-compose.yml` also defines a `mongodb` service, but the
> application code does not use MongoDB — all relational state is in PostgreSQL.

---

## Authentication & Authorization

- JWT access tokens + DB-backed refresh tokens (`helpers/jwt.py`, `RefreshToken`).
- Local email/password (`helpers/security.py` for hashing) and Google sign-in
  (`helpers/google_auth.py`), tracked by `users.auth_provider`.
- Email verification and single-use password reset tokens (the reset token embeds
  a fingerprint of the current password hash, so using it — or changing the
  password — invalidates it; see `helpers/jwt.py`).
- `helpers/auth_dependencies.get_current_user` guards feature endpoints;
  `services/project_access` enforces that a user owns the project/job they act on
  (`projects.owner_id`).

---

## Request Flow

### 1. File Upload Flow
```
POST /api/v1/data/upload/{project_id} + file   (auth required)
    → validate_uploaded_file (type whitelist, size ≤ FILE_MAX_SIZE)
    → get_project_for_user (owns project)
    → stream file to assets/files/{project_id}/<unique>_name
    → AssetModel.create_asset (asset_type=FILE)
    → { "signal": "success", "file_id": "<unique>_name" }
```

### 2. File Processing Flow
```
POST /api/v1/data/process/{project_id} + {chunk_size, overlap_size, do_reset}
    → load each asset (txt / pdf / markdown — markdown is split per Q&A section)
    → RecursiveCharacterTextSplitter → Document chunks
    → ChunkModel.insert_many_chunks (DataChunk rows)
    → { "signal": "success", "inserted_chunks": N, "processed_files": M }
```

### 3. Vector Indexing Flow
```
POST /api/v1/nlp/index/push/{project_id} + {do_reset}
    → page through chunks for the project
    → embedding_client.embed_text(texts)  (Cohere embed-multilingual-light-v3.0 → 384-dim)
    → vectordb_client.create_collection(collection_{size}_{project_id}, do_reset on first page)
    → vectordb_client.insert_many(texts, vectors, metadata, record_ids)  (batched)
    → { "signal": "insert_into_vectordb_success" }
```

### 4. Retrieval & Answer Generation Flow  ✅ implemented
Two entry points share the same retrieval + generation core:

```
Direct RAG:   POST /api/v1/nlp/index/answer/{project_id} + {text, limit}
Agent chat:   POST /api/v1/agent/chat/{project_id} + {message, session_id?, stream?}
    ↓
    (agent only) classify_intent — smalltalk shortcut vs. RAG, language detect
    ↓
    embed query → vectordb.search_by_vector(collection, query_vector, limit)
    ↓                                   → top-K chunks + similarity scores
    (optional) Cohere rerank — when RERANK_ENABLED, fetch RERANK_CANDIDATE_LIMIT
        candidates, reorder by cross-encoder relevance, keep the top `limit`;
        falls back to vector order on any rerank failure
    ↓
    build prompt from retrieved chunks (system + documents + footer template,
        temperature=0 for deterministic, non-echoing answers)
    ↓
    generation_client.generate_text(...)   (Cohere / OpenAI)
    ↓
    Response: { answer, sources[], tool_trace[] }
```

### 5. Agent Streaming Flow (SSE)
```
POST /api/v1/agent/chat/{project_id} + {"stream": true}
    → AgentController.chat_stream  (persists the user message up front)
    → AgentService.run_stream  (bypasses the LangGraph graph, reuses node methods)
        emits:  meta  {session_id, sources, tool_trace}   (after retrieval)
                delta {text}   × N                          (token chunks via
                                                             provider .generate_text_stream,
                                                             iterated off-thread)
                done  {answer, signal}                      (full text)
                error {detail}                              (on mid-stream failure)
    → assistant message persisted once, after the stream completes
       (a client disconnect persists nothing partial)
```
Providers stream via Cohere `chat_stream` / OpenAI `stream=True`; usage metadata
is captured from the final stream event so LangSmith token accounting still works.

### 6. Voice Flow
```
POST /api/v1/voice/stt    audio → faster-whisper → transcript     (auth)
POST /api/v1/voice/tts    text  → piper → audio/wav               (auth)
POST /api/v1/voice/chat/{project_id}
    audio → STT (whisper) → RAG answer → TTS (piper) → answer text + audio
    - upload validated (extension whitelist, size cap)
    - TTS voice chosen by the answer's language (ar → Arabic model, else default)
    - ffmpeg converts non-wav uploads to 16k mono wav for Whisper
```

### 7. Translation Flow (async job)
```
POST /translate/file + {project_id, file_id, source_lang?, target_lang?}
    → create TranslationJob (status=pending) → 202 {job_id}
    → BackgroundTask: read source asset bytes
        → LibreTranslateProvider.translate_file (multipart; api_key is a FORM field)
        → poll/download translatedFileUrl → save as TRANSLATED_FILE asset
        → job status → completed (or failed with error_message)
GET  /translate/status/{job_id}    → poll until completed/failed
GET  /translate/download/{job_id}  → FileResponse of the translated file
```

---

## Database Schema

### Table: projects
```sql
CREATE TABLE projects (
    project_id    INT PRIMARY KEY,
    project_uuid  UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    owner_id      INT REFERENCES users(id),        -- added: per-user ownership
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP
);
```
**Relationships**: 1-to-many with chunks, assets, agent_sessions; many-to-1 with users (owner).

### Table: assets
```sql
CREATE TABLE assets (
    asset_id          INT PRIMARY KEY,
    asset_uuid        UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    asset_type        VARCHAR NOT NULL,            -- "FILE" | "TRANSLATED_FILE"
    asset_name        VARCHAR NOT NULL,
    asset_size        INT NOT NULL,
    asset_config      JSONB,
    asset_project_id  INT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP NOT NULL DEFAULT NOW()
);
INDEX ix_asset_project_id, ix_asset_type;
```

### Table: chunks
```sql
CREATE TABLE chunks (
    chunk_id          INT PRIMARY KEY,
    chunk_uuid        UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    chunk_text        VARCHAR NOT NULL,
    chunk_metadata    JSONB,                       -- JSONB (migrated from JSON)
    chunk_order       INT NOT NULL,
    chunk_project_id  INT NOT NULL REFERENCES projects(project_id),
    chunk_asset_id    INT NOT NULL REFERENCES assets(asset_id),
    created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP
);
INDEX ix_chunk_project_id, ix_chunk_asset_id;
```

### Table: users
```sql
CREATE TABLE users (
    id              INT PRIMARY KEY,
    email           VARCHAR UNIQUE NOT NULL,
    username        VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR,                        -- NULL for Google-only accounts
    google_id       VARCHAR UNIQUE,                 -- added with Google sign-in
    auth_provider   VARCHAR,                        -- "local" | "google" | "both"
    is_verified     BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP
);
```

### Table: refresh_tokens
```sql
CREATE TABLE refresh_tokens (
    id          INT PRIMARY KEY,
    token       VARCHAR UNIQUE NOT NULL,
    user_id     INT NOT NULL REFERENCES users(id),
    expires_at  TIMESTAMP NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
```
A password reset deletes all of a user's refresh tokens (forces re-login).

### Table: agent_sessions
```sql
CREATE TABLE agent_sessions (
    session_id  INT PRIMARY KEY,
    project_id  INT NOT NULL REFERENCES projects(project_id),
    user_id     INT NOT NULL REFERENCES users(id),
    title       VARCHAR,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP
);
```

### Table: agent_messages
```sql
CREATE TABLE agent_messages (
    message_id        INT PRIMARY KEY,
    session_id        INT NOT NULL REFERENCES agent_sessions(session_id),
    role              VARCHAR NOT NULL,             -- "user" | "assistant"
    content           TEXT NOT NULL,
    message_metadata  JSONB,                        -- {sources, tool_trace}
    created_at        TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Table: translation_jobs
```sql
CREATE TABLE translation_jobs (
    job_id           INT PRIMARY KEY,
    project_id       INT NOT NULL REFERENCES projects(project_id),
    asset_id         INT NOT NULL REFERENCES assets(asset_id),   -- source file
    source_lang      VARCHAR,                       -- "auto" or a code
    target_lang      VARCHAR,
    status           VARCHAR,                       -- pending|processing|completed|failed
    result_asset_id  INT REFERENCES assets(asset_id),            -- translated file
    error_message    TEXT,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP
);
```

Migrations live in `src/models/db_schemes/minirag/alembic/versions/`; apply with
`alembic upgrade head` (see README). Tables are **not** auto-created on startup.
Under Docker this runs automatically (the backend entrypoint calls `alembic upgrade
head`, deriving the DB URL from the `POSTGRES_*` env vars); run it manually only when
running the app locally without Docker.

---

## Vector Database

The vector store is pluggable via `VECTOR_DB_BACKEND` (`VectorDBProviderFactory`):

- **PGVECTOR** (default) — vectors live in the same PostgreSQL via the `pgvector`
  extension. Simplest to operate; one datastore.
- **QDRANT** — local on-disk Qdrant at `assets/database/`.

Collection name: `collection_{embedding_size}_{project_id}` (e.g.
`collection_384_1000`). Each record stores the chunk text, the embedding vector,
and metadata payload.

```
Config:
  distance_method: DOT (configurable to cosine via VECTOR_DB_DISTANCE_METHOD)
  embedding_size:  384   (Cohere embed-multilingual-light-v3.0)
```

Search returns retrieved documents with `text`, `score`, and `meta_data`, which
the agent formats into `sources` (file paths stripped out before returning).

---

## Configuration & Environment

```env
# Application
APP_NAME / APP_DESCRIPTION / APP_VERSION
FILE_MAX_SIZE=10              # MB (enforced on data + voice uploads)
FILE_DEFAULT_CHUNK_SIZE=512000  # bytes per streamed read
STORAGE_ROOT=                # if set, files/db live under it (e.g. /data/rag)

# PostgreSQL
POSTGRES_USERNAME / POSTGRES_PASSWORD / POSTGRES_HOST / POSTGRES_PORT / POSTGRES_DB

# Auth
JWT_SECRET_KEY / JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES / REFRESH_TOKEN_EXPIRE_DAYS
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
FRONTEND_BASE_URL            # used to build verify/reset links in emails
RESEND_API_KEY / RESEND_FROM_EMAIL
GOOGLE_CLIENT_ID

# LLM
GENERATION_BACKEND=COHERE    # or OPENAI
GENERATION_MODEL_ID=command-a-03-2025
EMBEDDING_BACKEND=COHERE
EMBEDDING_MODEL_ID=embed-multilingual-light-v3.0
EMBEDDING_MODEL_SIZE=384
COHERE_API_KEY / OPENAI_API_KEY / OPENAI_API_URL
INPUT_DAFAULT_MAX_CHARACTERS=1024
GENERATION_DAFAULT_MAX_TOKENS / GENERATION_DAFAULT_TEMPERATURE

# Vector DB
VECTOR_DB_BACKEND=PGVECTOR   # or QDRANT
VECTOR_DB_PATH / VECTOR_DB_DISTANCE_METHOD

# Reranking (optional, Cohere; off by default)
RERANK_ENABLED=False
RERANK_MODEL_ID=rerank-multilingual-v3.0
RERANK_CANDIDATE_LIMIT=30     # candidates fetched before rerank; final count stays `limit`

# Agent
AGENT_DEFAULT_RETRIEVAL_LIMIT=5
AGENT_MAX_HISTORY_MESSAGES=10

# Translation
TRANSLATION_ENGINE=LIBRETRANSLATE
TRANSLATION_BASE_URL / TRANSLATION_FILE_ENDPOINT_URL
TRANSLATION_API_KEY          # only for API-key-protected instances
DEFAULT_TARGET_LANG=ar
TRANSLATION_TIMEOUT_SECONDS / TRANSLATION_MAX_RETRIES / TRANSLATION_RETRY_BACKOFF_SECONDS

# Voice — STT (faster-whisper)
STT_BACKEND=FASTER_WHISPER
STT_MODEL_SIZE / STT_DEVICE / STT_COMPUTE_TYPE
STT_TIMEOUT_SECONDS / STT_WARMUP_ON_STARTUP / STT_WARMUP_TIMEOUT_SECONDS

# Voice — TTS (piper)
TTS_BACKEND=PIPER
TTS_TIMEOUT_SECONDS=60
PIPER_EXE_PATH / PIPER_MODEL_PATH / PIPER_MODEL_PATH_AR
FFMPEG_PATH / FFMPEG_TIMEOUT_SECONDS

# Observability (optional)
LANGSMITH_TRACING / LANGSMITH_API_KEY / LANGSMITH_PROJECT / LANGSMITH_ENDPOINT
```

---

## Deployment Architecture

### Local / Docker

`docker/docker-compose.yml` runs the full stack (11 services). See
[docker/README.md](docker/README.md) for setup, env files, and monitoring.

```
docker/docker-compose.yml
├─ backend           (FastAPI, uvicorn :8000; entrypoint runs alembic upgrade head)
├─ frontend          (placeholder web UI — replace with the real frontend)
├─ nginx             (reverse proxy :80 → backend / grafana / prometheus)
├─ pgvector          (PostgreSQL + pgvector)         → relational + vector store
├─ mongodb           (defined but UNUSED by the app)
├─ qdrant            (available; not the active backend unless VECTOR_DB_BACKEND=QDRANT)
├─ libretranslate    (--load-only ar,en)             → translation
├─ prometheus        (scrapes backend /metrics + exporters)
├─ grafana           (dashboards; Prometheus datasource auto-provisioned)
├─ postgres-exporter (PostgreSQL metrics)
└─ node-exporter     (host metrics)

backend runtime paths:
├─ files     → assets/files/{project_id}/  (or {STORAGE_ROOT}/files)
├─ vectors   → PGVector (in PG) or assets/database/ (Qdrant)
└─ voice tmp → assets/voice/{project_id}/  (or {STORAGE_ROOT}/voice), deleted after use
```

Migrations run **automatically** on backend start (entrypoint → `alembic upgrade head`,
DB URL built from `POSTGRES_*` env vars). Monitoring: the app exposes `/metrics`
(`prometheus-fastapi-instrumentator`), Prometheus scrapes it, Grafana visualizes it.

### Railway
- Web service runs `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- PostgreSQL service + a persistent volume mounted at `/data`, `STORAGE_ROOT=/data/rag`.
- Healthcheck path: `/api/v1/welcome`.
- PGVECTOR is the simplest production option (no separate vector service).
- LibreTranslate / voice binaries need their own reachable services / Linux assets.

---

## Performance Characteristics

```
File Upload:        O(file_size)        - streamed read, size-capped
File Chunking:      O(file_size)        - recursive splitter
Vector Embedding:   O(chunks)           - LLM API calls (network-bound)
Vector Indexing:    O(chunks)           - batched inserts
Vector Search:      O(log n)            - ANN search
Answer Generation:  O(context)          - LLM API call (network-bound)
```

### Bottlenecks
1. **LLM API calls** — embedding and generation are network I/O bound (Cohere
   trial keys are rate-limited; the agent/eval paths retry with backoff).
2. **STT/TTS** — Whisper and Piper are CPU-bound; both run off the event loop in
   a thread with timeouts, but large models are slow on CPU.

### Optimization opportunities
1. Reranking after vector search (Cohere `rerank-multilingual-v3.0`) — implemented
   behind `RERANK_ENABLED` (off by default); enable and measure with `eval_rag.py`.
2. A larger STT model / Arabic-tuned settings for better transcription.
3. Caching embeddings; DB connection pooling.
4. Upgrading the embedding model to the full (1024-dim) multilingual model
   (requires re-indexing, since the collection name encodes the vector size).
```
