# RAG Knowledge Engine

Backend API for document ingestion, RAG question answering, a conversational
agent (with token streaming), translation, and voice workflows.

## Overview

The project provides:

- JWT authentication (email/password + Google sign-in, email verification, password reset)
- File upload and processing
- Chunking and embedding generation
- Vector search with `PGVector` or `Qdrant`
- Answer generation through LLM providers (`Cohere` / `OpenAI`)
- A conversational agent with session history and **Server-Sent Events streaming**
- Translation through provider-based integrations (`LibreTranslate`)
- Voice STT/TTS and voice chat endpoints, with automatic Arabic/English voice selection

## Current Structure

```text
src/
├── controllers/
├── helpers/
├── models/
├── routes/
├── services/          # agent service/tools, project access
├── stores/
│   ├── llm/
│   │   ├── providers/
│   │   ├── templete/
│   │   └── voice/
│   │       ├── providers/
│   │       ├── VoiceProviderFactory.py
│   │       └── VoiceProviderInterface.py
│   ├── translation/
│   └── Vectordb/
├── assets/
└── main.py
docs/                  # frontend integration guides (see below)
```

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — how the system works: layers, data models,
  request flows, DB schema, and configuration.
- **[PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md)** — the structural blueprint (layers,
  Interface/Factory/Provider pattern, conventions) for reproducing this architecture in
  a new project.
- **[docker/README.md](docker/README.md)** — the full Docker stack, env files, monitoring,
  Grafana dashboards, and troubleshooting.

## Authentication

All feature endpoints require a bearer token. Obtain one from the auth endpoints
and send it as `Authorization: Bearer <access_token>`.

- `POST /auth/register` — register, sends a verification email
- `POST /auth/login` — email/password login, returns access + refresh tokens
- `POST /auth/google` — Google sign-in with an ID token
- `POST /auth/refresh` — exchange a refresh token for a new access token
- `POST /auth/logout` — revoke a refresh token
- `GET /auth/verify-email` — verify an email via the emailed token
- `POST /auth/request-password-reset` — email a single-use reset link
- `POST /auth/reset-password` — set a new password with the reset token

Password-reset tokens are single-use and expire after
`PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` (default 30). A successful reset logs out
all existing sessions. See [docs/password-reset-api.md](docs/password-reset-api.md).

## Agent Chat & Streaming

`POST /api/v1/agent/chat/{project_id}` runs the conversational RAG agent with
session history. Set `"stream": true` in the request body to receive the answer
token-by-token over Server-Sent Events (`text/event-stream`); otherwise a single
JSON response is returned (unchanged).

- `POST /api/v1/agent/chat/{project_id}` — chat (supports `stream: true`)
- `GET /api/v1/agent/sessions/{project_id}` — list sessions
- `GET /api/v1/agent/sessions/{project_id}/{session_id}` — session with messages
- `DELETE /api/v1/agent/sessions/{project_id}/{session_id}` — delete a session

SSE event order: `meta` (session id + sources + tool trace) → `delta`* (text
chunks) → `done` (full answer). Mid-generation failures emit an `error` event.
See [docs/agent-streaming-frontend-prompt.md](docs/agent-streaming-frontend-prompt.md).

## RAG Chat vs Agent — prompts

Both the direct RAG chat (`POST /api/v1/nlp/index/answer/{project_id}`) and the
agent (`POST /api/v1/agent/chat/{project_id}`) answer **only from the project's
indexed files**. They differ in the system prompt each uses, selected by
`template_group` in `NLPController._build_rag_prompt` (default `"rag"`):

- **Agent → `rag` template.** A customer-support persona locked to answering the
  user's question from the documents. Unchanged; the agent never passes
  `template_group`, so it always uses this.
- **RAG chat → `rag_chat` template.** A general assistant that can not only answer
  but also **translate, summarize, rephrase, or generate new text** — still using
  the file content only. It also replies in the request's language *unless* the
  user asks for another language (so translation requests work).

Prompt files live in `src/stores/llm/templete/local/{en,ar}/` as `rag.py`
(agent) and `rag_chat.py` (chat). Editing one does not affect the other.

## Voice Architecture

Voice follows the same provider pattern used elsewhere in the project.

- `src/stores/llm/voice/VoiceProviderInterface.py` — STT/TTS contract.
- `src/stores/llm/voice/VoiceProviderFactory.py` — creates the configured provider.
- `src/stores/llm/voice/providers/LocalVoiceProvider.py` — local STT with
  `faster-whisper` and local TTS with `piper`.
- `src/controllers/VoiceController.py` — thin; delegates to the provider.

Current supported combination:

- `STT_BACKEND=FASTER_WHISPER`
- `TTS_BACKEND=PIPER`

### Per-language TTS voice

Piper voices are single-language, so an Arabic answer spoken with an English
voice is unintelligible. Configure a voice per language and the backend picks one
automatically based on the text's language:

- `PIPER_MODEL_PATH` — default/English voice
- `PIPER_MODEL_PATH_AR` — Arabic voice (e.g. `ar_JO-kareem-medium.onnx`); used
  when the text is detected as Arabic. Falls back to the default voice if unset.

`/voice/chat` selects the voice from the **answer's** language, so an English
question with an Arabic answer is spoken in Arabic.

## Requirements

- Python 3.10+
- PostgreSQL
- `PGVector` or `Qdrant`
- A configured LLM provider such as `Cohere` or `OpenAI`

For voice features:

- `faster-whisper`
- `piper` (and an Arabic + English voice model if you serve both languages)
- `ffmpeg` if you want to upload non-`wav` audio such as `mp3` or `m4a`

For translation:

- A reachable `LibreTranslate` instance (the bundled `docker/docker-compose.yml`
  runs one loaded with Arabic + English).

## Installation

From the repository root:

```bash
git clone https://github.com/AbdElrhmanmwadi/rag-knowledge-engine.git
cd rag-knowledge-engine
pip install -r requirements.txt
```

If you use Conda, activate your environment first (this project is developed
against a Conda env, e.g. `conda activate mini-rag-full-win`).

### Full Docker stack (recommended)

`docker/docker-compose.yml` runs the **entire application** as an 11-service stack:
the FastAPI backend, a placeholder frontend, an Nginx reverse proxy, PostgreSQL
(pgvector), MongoDB, Qdrant, LibreTranslate, and a monitoring stack (Prometheus,
Grafana, postgres-exporter, node-exporter).

```bash
cd docker
# create the per-service env files from the examples first (see docker/README.md)
docker compose up --build -d
```

- App via Nginx: http://localhost · API docs: http://localhost:8000/docs
- Grafana: http://localhost/grafana/ · Prometheus: http://localhost/prometheus/
- **Migrations run automatically** on backend start (the entrypoint runs
  `alembic upgrade head`, building the DB URL from the `POSTGRES_*` env vars).

Full setup, env files, monitoring and dashboards, and troubleshooting are documented
in **[docker/README.md](docker/README.md)**.

### Backing services only

To bring up just the databases/translation (e.g. when running the app locally):

```bash
docker compose -f docker/docker-compose.yml up -d pgvector mongodb libretranslate
```

Or provide your own PostgreSQL with the `vector` extension and point `.env`/the
Alembic URL at it.

### Database migrations (required)

The app does **not** create tables on startup — run the Alembic migrations once
against your database before first launch (and after pulling new migrations).

> **Docker users:** you can skip this section — the `backend` container's entrypoint
> runs `alembic upgrade head` automatically on start (it derives the DB URL from the
> `POSTGRES_*` env vars). The steps below are for running the app **locally** without Docker.

1. Copy the Alembic config and set your database URL:

   ```bash
   cp src/models/db_schemes/minirag/alembic.ini.example src/models/db_schemes/minirag/alembic.ini
   # edit alembic.ini and set:
   # sqlalchemy.url = postgresql+psycopg2://<user>:<password>@<host>/<db>
   ```

   `alembic.ini` is gitignored (it holds a real connection string), so each
   environment creates its own.

2. Apply all migrations:

   ```bash
   cd src/models/db_schemes/minirag
   alembic upgrade head
   ```

   This creates the projects, assets, data chunks, users/auth, agent sessions,
   and translation-job tables.

## Environment Setup

Copy `src/.env.example` to `src/.env` and update the values.

Important sections include:

```env
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=yourpassword
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rag_db

GENERATION_BACKEND=COHERE
EMBEDDING_BACKEND=COHERE
COHERE_API_KEY=your_key

VECTOR_DB_BACKEND=PGVECTOR

# Auth
JWT_SECRET_KEY=your_secret
JWT_ALGORITHM=HS256
# Base URL of the frontend that hosts the verify-email / reset-password pages.
# Used to build the links in outgoing emails — set this to the real frontend URL.
FRONTEND_BASE_URL=https://your-domain.com
RESEND_API_KEY=your_resend_key

# Translation (LibreTranslate)
TRANSLATION_ENGINE=LIBRETRANSLATE
TRANSLATION_BASE_URL=http://localhost:5000/translate
TRANSLATION_FILE_ENDPOINT_URL=http://localhost:5000/translate/file
DEFAULT_TARGET_LANG=ar
# TRANSLATION_API_KEY is only needed for an API-key-protected instance
# (e.g. libretranslate.com); leave empty for a local/self-hosted instance.

# Voice — STT
STT_BACKEND=FASTER_WHISPER
STT_MODEL_SIZE=tiny
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_TIMEOUT_SECONDS=300
STT_WARMUP_ON_STARTUP=True
STT_WARMUP_TIMEOUT_SECONDS=600

# Voice — TTS
TTS_BACKEND=PIPER
TTS_TIMEOUT_SECONDS=60
PIPER_EXE_PATH=C:/path/to/piper.exe
PIPER_MODEL_PATH=C:/path/to/en_US-lessac-medium.onnx
PIPER_MODEL_PATH_AR=C:/path/to/ar_JO-kareem-medium.onnx

# Optional for mp3/m4a support
FFMPEG_PATH=C:/path/to/ffmpeg.exe
```

## Run

Because the app entrypoint and `.env` live under `src/`, run the server from `src`:

```bash
cd src
uvicorn main:app --host 0.0.0.0 --port 8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## Deploy on Railway

The repository includes:

- `Dockerfile`
- `railway.json`
- `.dockerignore`

Recommended Railway setup:

1. Create a web service from this repository.
2. Add a PostgreSQL service.
3. Attach a persistent `Volume` and mount it at `/data`.
4. Set `STORAGE_ROOT=/data/rag`.
5. Add the required environment variables from `src/.env.example`.

Recommended start behavior on Railway:

- The container runs `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Healthcheck path: `/api/v1/welcome`

Notes:

- File uploads and temporary voice files should use the mounted volume through `STORAGE_ROOT`.
- `PGVECTOR` is the simplest production option on Railway for this project.
- If you use `LIBRETRANSLATE`, point `TRANSLATION_BASE_URL` and `TRANSLATION_FILE_ENDPOINT_URL` to another Railway service or an external API.
- Voice features may need extra Linux-compatible runtime assets for `piper` models and binaries.

## Main API Endpoints

All endpoints below require `Authorization: Bearer <access_token>` except
`GET /api/v1/welcome` and the auth endpoints.

### Base

- `GET /api/v1/welcome` — app name/description/version (also used as healthcheck)

### Auth

- `POST /auth/register`, `POST /auth/login`, `POST /auth/google`
- `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/verify-email`
- `POST /auth/request-password-reset`, `POST /auth/reset-password`

### Data

- `POST /api/v1/data/upload/{project_id}`
- `POST /api/v1/data/process/{project_id}`
- `GET /api/v1/data/files/{project_id}`
- `GET /api/v1/data/file/{project_id}/{file_id}`
- `DELETE /api/v1/data/delete/{project_id}/{file_id}`
- `DELETE /api/v1/data/delete_all/{project_id}`

### NLP

- `POST /api/v1/nlp/index/push/{project_id}`
- `GET /api/v1/nlp/index/info/{project_id}`
- `POST /api/v1/nlp/index/search/{project_id}` — vector search (no generation)
- `POST /api/v1/nlp/index/answer/{project_id}` — direct RAG answer (no agent/session)

### Agent

- `POST /api/v1/agent/chat/{project_id}` — chat; `stream: true` for SSE
- `GET /api/v1/agent/sessions/{project_id}`
- `GET /api/v1/agent/sessions/{project_id}/{session_id}`
- `DELETE /api/v1/agent/sessions/{project_id}/{session_id}`

### Translation

Asynchronous job flow (submit → poll → download):

- `POST /translate/file` — queue a translation job (returns `job_id`, 202)
- `GET /translate/status/{job_id}` — poll job status
- `GET /translate/download/{job_id}` — download the translated file

### Voice

- `POST /api/v1/voice/stt` — multipart audio upload, returns transcript text.
- `POST /api/v1/voice/tts` — JSON body, returns `audio/wav`.
- `POST /api/v1/voice/chat/{project_id}` — audio in → STT → RAG → answer text + audio out.

## Voice Notes

- `/stt` and `/tts` require authentication, like the rest of the API.
- `wav` uploads work without `ffmpeg`; `mp3`, `m4a`, and similar require `ffmpeg`.
- Uploads are validated: unsupported types return `400 file_type_not_supported`,
  oversized files return `413 file_size_exceeded` (bounded by `FILE_MAX_SIZE`).
- `/voice/chat` returns a 404 for an unknown project (it does not auto-create one).
- When returning raw audio (`return_audio_base64=false`), the transcript is in the
  percent-encoded `X-Transcript` header — decode it with `decodeURIComponent`.
- First startup may be slower while the Whisper model loads; `faster-whisper` may
  download it on first use if it is not cached.

## Download Whisper Model

To download the STT model manually before starting the server, use the same
Python environment that runs the app.

Example for the `tiny` model on Windows:

```powershell
C:\Users\msi\miniconda3\envs\mini-rag-full-win\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Systran/faster-whisper-tiny', force_download=True)"
```

Then verify the model can load:

```powershell
C:\Users\msi\miniconda3\envs\mini-rag-full-win\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cpu', compute_type='int8'); print('ok')"
```

Replace `tiny` with `small` (or larger) for better accuracy, especially for Arabic.

## Frontend Integration Guides

Ready-to-hand guides for the frontend live in `docs/`:

- [docs/password-reset-api.md](docs/password-reset-api.md) — password reset flow
- [docs/agent-streaming-frontend-prompt.md](docs/agent-streaming-frontend-prompt.md) — SSE chat streaming
- [docs/voice-frontend-prompt.md](docs/voice-frontend-prompt.md) — voice endpoints
- [docs/feedback-frontend-prompt.md](docs/feedback-frontend-prompt.md) — answer feedback (👍/👎) + analytics
- [docs/translation-frontend-prompt.md](docs/translation-frontend-prompt.md) — translation job flow
- [docs/translation-libretranslate.md](docs/translation-libretranslate.md) — LibreTranslate provider contract

## Response Signals

Endpoints return a `signal` field from `ResponseStatus`, including:

- Agent: `agent_chat_success`, `agent_sessions_success`, `agent_session_success`, `agent_session_deleted`
- Translation: `translation_job_created_success`, `translation_status_success`, `translation_failed`
- Voice: `stt_success`, `stt_failed`, `stt_timeout`, `tts_failed`, `voice_chat_success`, `voice_chat_failed`, `voice_chat_timeout`
- Upload validation: `file_type_not_supported`, `file_size_exceeded`
```
