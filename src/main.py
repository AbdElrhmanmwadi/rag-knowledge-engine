from fastapi import FastAPI
from dotenv import load_dotenv
from routes import base, data
load_dotenv(".env")
app = FastAPI()
app.include_router(base.base_router)
app.include_router(data.data_router)
