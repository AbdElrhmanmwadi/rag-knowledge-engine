from fastapi import Depends, FastAPI,APIRouter
from helpers.config import Settings, get_settings
import os

base_router = APIRouter(
    prefix="/api/v1",
    tags=["Base Routes"]
)
@base_router.get("/welcome")
async def welcome(app_settings: Settings = Depends(get_settings)): 
    app_name = app_settings.APP_NAME
    app_description = app_settings.APP_DESCRIPTION
    app_version = app_settings.APP_VERSION
    
    return {"app_name": app_name, "description": app_description, "version": app_version}

