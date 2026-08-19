from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, model_validator
from typing import List,Optional

class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_NAME: str
    APP_DESCRIPTION: str
    APP_VERSION: str
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int
    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str  
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_URL: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None
    TRANSLATION_ENGINE: str 
    TRANSLATION_API_KEY: Optional[str] = None
    TRANSLATION_BASE_URL: str = "http://localhost:5000/translate"
    TRANSLATION_FILE_ENDPOINT_URL: str = "http://localhost:5000/translate/file"
    TRANSLATION_TIMEOUT_SECONDS: int = 60
    TRANSLATION_MAX_RETRIES: int = 2
    TRANSLATION_RETRY_BACKOFF_SECONDS: float = 1.0
    DEFAULT_TARGET_LANG: str = "ar"

    GENERATION_MODEL_ID: Optional[str] = None
    EMBEDDING_MODEL_ID: Optional[str] = None
    EMBEDDING_MODEL_SIZE: Optional[int] = None
    INPUT_DAFAULT_MAX_CHARACTERS: Optional[int] = None
    GENERATION_DAFAULT_MAX_TOKENS: Optional[int] = None
    GENERATION_DAFAULT_TEMPERATURE: Optional[float] = None
    VECTOR_DB_BACKEND_LITERAL: Optional[List[str]] = None
    VECTOR_DB_BACKEND: str 
    VECTOR_DB_PGVEC_INDEX_THRESHOLD : int = 50
    VECTOR_DB_PATH: str
    VECTOR_DB_DISTANCE_METHOD: str
    STORAGE_ROOT: Optional[str] = None
    PRIMARY_LANG: str 
    DEFAULT_LANG: str

    # =========================
    # Voice (STT / TTS)
    # =========================
    STT_BACKEND: str = "FASTER_WHISPER"
    STT_MODEL_SIZE: str = "small"
    STT_DEVICE: str = "cpu"
    STT_COMPUTE_TYPE: str = "int8"
    STT_TIMEOUT_SECONDS: int = 180
    STT_WARMUP_ON_STARTUP: bool = True
    STT_WARMUP_TIMEOUT_SECONDS: int = 1000

    TTS_BACKEND: str = "PIPER"
    TTS_TIMEOUT_SECONDS: int = 60
    PIPER_EXE_PATH: Optional[str] = None
    PIPER_MODEL_PATH: Optional[str] = None
    # Arabic voice; answers detected as Arabic are synthesized with this model.
    PIPER_MODEL_PATH_AR: Optional[str] = None

    # Optional: allow non-wav uploads (mp3/m4a/...) and convert via ffmpeg
    FFMPEG_PATH: Optional[str] = None
    FFMPEG_TIMEOUT_SECONDS: int = 60

    # =========================
    # Reranking (optional; Cohere cross-encoder reorders vector hits)
    # =========================
    # Off by default: when False, retrieval behaves exactly as before.
    RERANK_ENABLED: bool = False
    RERANK_MODEL_ID: str = "rerank-multilingual-v3.0"
    # How many candidates to pull from the vector DB before reranking. The final
    # count returned to the caller stays the requested `limit`.
    RERANK_CANDIDATE_LIMIT: int = 30

    # =========================
    # Agent
    # =========================
    AGENT_DEFAULT_RETRIEVAL_LIMIT: int = 5
    AGENT_MAX_TOOL_STEPS: int = 4
    AGENT_MAX_OUTPUT_TOKENS: int = 500
    # Number of most-recent prior messages fed back to the model as conversation context
    AGENT_MAX_HISTORY_MESSAGES: int = 10

    # =========================
    # Semantic answer cache (optional)
    # When enabled, a question semantically similar (>= threshold) to a previously
    # answered one returns the stored answer instantly, skipping retrieval + generation.
    # =========================
    ANSWER_CACHE_ENABLED: bool = False
    ANSWER_CACHE_SIMILARITY_THRESHOLD: float = 0.95

    # =========================
    # Observability (LangSmith)
    # Accept both the modern LANGSMITH_* and the legacy LANGCHAIN_* env names.
    # =========================
    LANGSMITH_TRACING: bool = Field(
        default=False,
        validation_alias=AliasChoices("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"),
    )
    LANGSMITH_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"),
    )
    LANGSMITH_PROJECT: str = Field(
        default="rag-knowledge-engine",
        validation_alias=AliasChoices("LANGSMITH_PROJECT", "LANGCHAIN_PROJECT"),
    )
    LANGSMITH_ENDPOINT: str = Field(
        default="https://api.smith.langchain.com",
        validation_alias=AliasChoices("LANGSMITH_ENDPOINT", "LANGCHAIN_ENDPOINT"),
    )

    # =========================
    # Auth
    # =========================
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "Voxora <noreply@your-domain.com>"
    FRONTEND_BASE_URL: str = "https://your-domain.com"
    GOOGLE_CLIENT_ID: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.APP_ENV.lower() in {"production", "prod"}:
            unsafe_secrets = {"", "replace-with-a-strong-random-secret", "change-me", "change_me"}
            if self.JWT_SECRET_KEY in unsafe_secrets or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must be a unique secret of at least 32 characters in production")
            if self.FRONTEND_BASE_URL.startswith("http://"):
                raise ValueError("FRONTEND_BASE_URL must use HTTPS in production")
        return self

@lru_cache
def get_settings():
    """Load settings only when the application starts, not during module import."""
    return Settings()
