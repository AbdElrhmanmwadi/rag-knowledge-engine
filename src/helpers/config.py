from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List,Optional

class Settings(BaseSettings):
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

    OPENAI_API_KEY: str = None
    OPENAI_API_URL: str = None
    COHERE_API_KEY: str = None
    TRANSLATION_ENGINE: str 
    TRANSLATION_API_KEY: str = None
    TRANSLATION_BASE_URL: str = "http://localhost:5000/translate"
    TRANSLATION_FILE_ENDPOINT_URL: str = "http://localhost:5000/translate/file"
    TRANSLATION_TIMEOUT_SECONDS: int = 60
    TRANSLATION_MAX_RETRIES: int = 2
    TRANSLATION_RETRY_BACKOFF_SECONDS: float = 1.0
    DEFAULT_TARGET_LANG: str = "ar"

    GENERATION_MODEL_ID: str = None
    EMBEDDING_MODEL_ID: str = None
    EMBEDDING_MODEL_SIZE: int = None
    INPUT_DAFAULT_MAX_CHARACTERS: int = None
    GENERATION_DAFAULT_MAX_TOKENS: int = None
    GENERATION_DAFAULT_TEMPERATURE: float = None
    VECTOR_DB_BACKEND_LITERAL: List[str] = None
    VECTOR_DB_BACKEND: str 
    VECTOR_DB_PGVEC_INDEX_THRESHOLD : int = 50
    VECTOR_DB_PATH: str
    VECTOR_DB_DISTANCE_METHOD: str
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
    PIPER_EXE_PATH: str = None
    PIPER_MODEL_PATH: str = None

    # Optional: allow non-wav uploads (mp3/m4a/...) and convert via ffmpeg
    FFMPEG_PATH: Optional[str] = None
    FFMPEG_TIMEOUT_SECONDS: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()   
def get_settings():
        return settings
