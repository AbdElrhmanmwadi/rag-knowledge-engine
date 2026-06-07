import asyncio
import logging
import os

from fastapi import FastAPI
from controllers.VoiceController import VoiceController
from routes import agent, auth_router, base, data, nlp, translation_router, voice
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from helpers.config import get_settings
from stores.llm.providers.LLMProviderFactory import LLMProviderFactory
from stores.llm.voice import VoiceProviderFactory

from stores.translation.TranslationProviderFactory import TranslationProviderFactory
from stores.Vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from stores.llm.template_parser import TemplateParser  
from fastapi.middleware.cors import CORSMiddleware 


app = FastAPI()

app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:5173", "http://localhost:5174"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)
logger = logging.getLogger("uvicorn.error")


async def warm_up_stt(app: FastAPI, settings) -> None:
    try:
        await asyncio.wait_for(
            asyncio.to_thread(app.state.voice_controller.warm_up_stt),
            timeout=settings.STT_WARMUP_TIMEOUT_SECONDS,
        )
        logger.info("STT warm-up completed")
    except asyncio.TimeoutError:
        logger.warning("STT warm-up timed out after %ss", settings.STT_WARMUP_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("STT warm-up failed")


@app.on_event("startup")
async def startup_event():
    settings = get_settings()
    print("PGHOST =", os.getenv("PGHOST"))
    print("DATABASE_URL =", os.getenv("DATABASE_URL"))
    # Railway توفر DATABASE_URL تلقائياً, أو استخدم المتغيرات اليدوية
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # تحويل postgres إلى postgresql+asyncpg إذا لزم الحال
        postgres_conn = database_url.replace('postgres://', 'postgresql+asyncpg://')
    else:
        postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    
    app.db_engine = create_async_engine(postgres_conn)
    app.db_client = sessionmaker(app.db_engine, expire_on_commit=False, class_=AsyncSession)
    LLM_Provider_Factory=LLMProviderFactory(settings)
    translation_provider_factory = TranslationProviderFactory(settings)
    voice_provider_factory = VoiceProviderFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(config=settings,db_client=app.db_client)
    


    app.generation_client = LLM_Provider_Factory.create(provider=settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(model_id = settings.GENERATION_MODEL_ID)

    app.embedding_client = LLM_Provider_Factory.create(provider=settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID,
                                             embedding_size=settings.EMBEDDING_MODEL_SIZE)
    app.translation_provider = translation_provider_factory.create(provider=settings.TRANSLATION_ENGINE)
    
    app.vectordb_client = vectordb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    if app.vectordb_client is None:
        raise ValueError(f"Failed to create vector database client. Unsupported provider: {settings.VECTOR_DB_BACKEND}. Supported providers: QDRANT, PGVECTOR")
    voice_provider = voice_provider_factory.create(
        stt_provider=settings.STT_BACKEND,
        tts_provider=settings.TTS_BACKEND,
    )
    app.state.voice_controller = VoiceController(settings=settings, voice_provider=voice_provider)
    # Retry connecting to vector DB because managed databases may not be immediately ready
    max_retries = 6
    retry_delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            await app.vectordb_client.connect()
            break
        except Exception as e:
            logger.warning("Attempt %s/%s: vectordb connect failed: %s", attempt, max_retries, e)
            if attempt == max_retries:
                logger.exception("vectordb connection failed after %s attempts", max_retries)
                raise
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)
    if settings.STT_WARMUP_ON_STARTUP:
        asyncio.create_task(warm_up_stt(app, settings))
    app.template_parser= TemplateParser(
        language=settings.PRIMARY_LANG,
        defult_language=settings.DEFAULT_LANG

    )

    
        

@app.on_event("shutdown")
async def shutdown_event():
    await app.db_engine.dispose()
    await app.vectordb_client.disconnect()

app.include_router(base.base_router)
app.include_router(auth_router.auth_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
app.include_router(translation_router.translation_router)
app.include_router(voice.voice_router)
app.include_router(agent.agent_router)
