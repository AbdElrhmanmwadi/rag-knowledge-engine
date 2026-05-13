# RAG Knowledge Engine

Backend API for document ingestion, RAG question answering, translation, and voice workflows.

## Overview

The project provides:

- File upload and processing
- Chunking and embedding generation
- Vector search with `PGVector` or `Qdrant`
- Answer generation through LLM providers
- Translation through provider-based integrations
- Voice STT/TTS and voice chat endpoints

## Current Structure

```text
src/
├── controllers/
├── helpers/
├── models/
├── routes/
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
```

## Voice Architecture

Voice was refactored to follow the same provider pattern used elsewhere in the project.

- `src/stores/llm/voice/VoiceProviderInterface.py`
  Defines the STT/TTS contract.
- `src/stores/llm/voice/VoiceProviderFactory.py`
  Creates the configured voice provider.
- `src/stores/llm/voice/providers/LocalVoiceProvider.py`
  Implements local STT with `faster-whisper` and local TTS with `piper`.
- `src/controllers/VoiceController.py`
  Stays thin and delegates voice work to the provider.

Current supported combination:

- `STT_BACKEND=FASTER_WHISPER`
- `TTS_BACKEND=PIPER`

## Requirements

- Python 3.10+
- PostgreSQL
- `PGVector` or `Qdrant`
- A configured LLM provider such as `Cohere` or `OpenAI`

For voice features:

- `faster-whisper`
- `piper`
- `ffmpeg` if you want to upload non-`wav` audio such as `mp3` or `m4a`

## Installation

From the repository root:

```bash
git clone https://github.com/AbdElrhmanmwadi/rag-knowledge-engine.git
cd rag-knowledge-engine
pip install -r requirements.txt
```

If you use Conda, activate your environment first.

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

STT_BACKEND=FASTER_WHISPER
STT_MODEL_SIZE=tiny
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_TIMEOUT_SECONDS=300
STT_WARMUP_ON_STARTUP=True
STT_WARMUP_TIMEOUT_SECONDS=600

TTS_BACKEND=PIPER
PIPER_EXE_PATH=C:/path/to/piper.exe
PIPER_MODEL_PATH=C:/path/to/model.onnx

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

## Main API Endpoints

### Data

- `POST /api/v1/data/upload/{project_id}`
- `POST /api/v1/data/process/{project_id}`
- `GET /api/v1/data/files/{project_id}`
- `DELETE /api/v1/data/delete/{project_id}/{file_id}`
- `DELETE /api/v1/data/delete_all/{project_id}`

### NLP

- `POST /api/v1/nlp/index/push/{project_id}`
- `GET /api/v1/nlp/index/info/{project_id}`

### Voice

- `POST /api/v1/voice/stt`
  Accepts multipart audio upload and returns transcript text.
- `POST /api/v1/voice/tts`
  Accepts JSON body and returns `audio/wav`.
- `POST /api/v1/voice/chat/{project_id}`
  Accepts audio, runs STT, asks the RAG pipeline, and returns answer text plus audio.

## Voice Notes

- `wav` uploads work without `ffmpeg`.
- `mp3`, `m4a`, and similar formats require `ffmpeg`.
- First startup may be slower while the Whisper model loads.
- If the Whisper model is not already cached, `faster-whisper` may download it on first use.

## Download Whisper Model

If you want to download the STT model manually before starting the server, use the same Python environment that runs the app.

Example for the `tiny` model on Windows:

```powershell
C:\Users\msi\miniconda3\envs\mini-rag-full-win\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Systran/faster-whisper-tiny', force_download=True)"
```

Then verify the model can load:

```powershell
C:\Users\msi\miniconda3\envs\mini-rag-full-win\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cpu', compute_type='int8'); print('ok')"
```

If you want to use another model size, replace `tiny` with values such as `small`.

## Response Signals

Voice endpoints now use shared response signals from `ResponseStatus`, including:

- `stt_success`
- `stt_failed`
- `stt_timeout`
- `tts_failed`
- `voice_chat_success`
- `voice_chat_failed`
- `voice_chat_timeout`

## Author

Abd elrahman Ahmed wadi

- GitHub: `https://github.com/AbdElrhmanmwadi`
