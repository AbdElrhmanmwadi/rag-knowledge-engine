# =========================================================================
# Backend (FastAPI) application config — Docker.
# Copy to .env.app and fill in real secrets (COHERE_API_KEY, JWT_SECRET_KEY...).
# Hostnames below are Docker Compose service names, not localhost.
# =========================================================================
APP_NAME="RAG Knowledge Engine"
APP_DESCRIPTION="A knowledge engine that uses Retrieval-Augmented Generation (RAG) to provide accurate and relevant information based on user queries."
APP_VERSION="1.0.0"
FILE_MAX_SIZE=10            # MB
FILE_DEFAULT_CHUNK_SIZE=512000  # 0.5 MB
STORAGE_ROOT="/data/rag"

# ========================= Postgres (pgvector service) =========================
POSTGRES_USERNAME="postgres"
POSTGRES_PASSWORD="change_me"
POSTGRES_HOST="pgvector"
POSTGRES_PORT=5432
POSTGRES_DB="minirag-v1"

# ========================= LLM Config =========================
GENERATION_BACKEND="COHERE"
EMBEDDING_BACKEND="COHERE"
OPENAI_API_URL=""
COHERE_API_KEY="your_cohere_api_key"
OPENAI_API_KEY="your_openai_api_key"
GENERATION_MODEL_ID=command-a-03-2025
EMBEDDING_MODEL_ID="embed-multilingual-light-v3.0"
EMBEDDING_MODEL_SIZE=384
INPUT_DAFAULT_MAX_CHARACTERS=1024
GENERATION_DAFAULT_MAX_TOKENS=1024
GENERATION_DAFAULT_TEMPERATURE=0.1

# ========================= Vector DB Config =========================
# Active backend is PGVECTOR (uses the pgvector Postgres service above).
# A standalone Qdrant service is also available at http://qdrant:6333 if you switch.
VECTOR_DB_BACKEND_LITERAL=["QDRANT", "PGVECTOR"]
VECTOR_DB_BACKEND="PGVECTOR"
VECTOR_DB_PATH="qdrant_db"
VECTOR_DB_DISTANCE_METHOD="cosine"
VECTOR_DB_PGVEC_INDEX_THRESHOLD=100

# ========================= Template / Language =========================
PRIMARY_LANG="en"
DEFAULT_LANG="en"

# ========================= Translation (libretranslate service) =========================
TRANSLATION_ENGINE="LIBRETRANSLATE"
TRANSLATION_API_KEY=""
TRANSLATION_BASE_URL="http://libretranslate:5000/translate"
TRANSLATION_FILE_ENDPOINT_URL="http://libretranslate:5000/translate/file"
TRANSLATION_TIMEOUT_SECONDS=60
TRANSLATION_MAX_RETRIES=2
TRANSLATION_RETRY_BACKOFF_SECONDS=1.0
DEFAULT_TARGET_LANG="ar"

# ========================= Voice (STT / TTS) =========================
STT_BACKEND=FASTER_WHISPER
STT_MODEL_SIZE=tiny
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_TIMEOUT_SECONDS=300
STT_WARMUP_ON_STARTUP=False
STT_WARMUP_TIMEOUT_SECONDS=600
TTS_BACKEND=PIPER
TTS_TIMEOUT_SECONDS=60
PIPER_EXE_PATH=""
PIPER_MODEL_PATH=""
PIPER_MODEL_PATH_AR=""
# ffmpeg is installed in the Docker image, so FFMPEG_PATH is usually not needed.

# ========================= Agent =========================
AGENT_DEFAULT_RETRIEVAL_LIMIT=5
AGENT_MAX_TOOL_STEPS=4
AGENT_MAX_OUTPUT_TOKENS=500
AGENT_MAX_HISTORY_MESSAGES=10

# ========================= Reranking (optional, Cohere) =========================
RERANK_ENABLED=False
RERANK_MODEL_ID=rerank-multilingual-v3.0
RERANK_CANDIDATE_LIMIT=30

# ========================= Semantic answer cache (optional) =========================
ANSWER_CACHE_ENABLED=False
ANSWER_CACHE_SIMILARITY_THRESHOLD=0.95

# ========================= Observability (LangSmith) =========================
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=""
LANGSMITH_PROJECT="rag-knowledge-engine"
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"

# ========================= Auth =========================
JWT_SECRET_KEY="replace-with-a-strong-random-secret"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24
RESEND_API_KEY="re_replace_with_resend_api_key"
RESEND_FROM_EMAIL="Voxora <noreply@your-domain.com>"
FRONTEND_BASE_URL="http://localhost"
GOOGLE_CLIENT_ID=""
