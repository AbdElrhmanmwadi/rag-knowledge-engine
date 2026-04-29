from fastapi import FastAPI
from routes import base, data,nlp,translation_router
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from helpers.config import get_settings
from stores.llm.providers.LLMProviderFactory import LLMProviderFactory

from stores.translation.TranslationProviderFactory import TranslationProviderFactory
from stores.Vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from stores.llm.template_parser import TemplateParser   


app = FastAPI()
@app.on_event("startup")
async def startup_event():
    settings = get_settings()
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    app.db_engine = create_async_engine(postgres_conn)
    app.db_client = sessionmaker(app.db_engine, expire_on_commit=False, class_=AsyncSession)
    LLM_Provider_Factory=LLMProviderFactory(settings)
    translation_provider_factory = TranslationProviderFactory(settings)
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
    
    await app.vectordb_client.connect()
    app.template_parser= TemplateParser(
        language=settings.PRIMARY_LANG,
        defult_language=settings.DEFAULT_LANG

    )

    
        

@app.on_event("shutdown")
async def shutdown_event():
    await app.db_engine.dispose()
    await app.vectordb_client.disconnect()

app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
app.include_router(translation_router.translation_router)
