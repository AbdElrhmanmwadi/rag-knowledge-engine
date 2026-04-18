from fastapi import FastAPI
<<<<<<< HEAD
from routes import base, data
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from helpers.config import get_settings
app = FastAPI()
@app.on_event("startup")
async def startup_event():
    settings = get_settings()
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    app.db_engine = create_async_engine(postgres_conn)
    app.db_client = sessionmaker(app.db_engine, expire_on_commit=False, class_=AsyncSession)


async def shutdown_event():
    await app.db_engine.dispose()


app.include_router(base.base_router)
app.include_router(data.data_router)
=======
from dotenv import load_dotenv
from routes import base, data
load_dotenv(".env")
app = FastAPI()
app.include_router(base.base_router)
app.include_router(data.data_router)
>>>>>>> 9cd4fe5c8b3f3af73134140deadab29b34468848
