from fastapi import FastAPI,Depends,APIRouter, UploadFile,status
from fastapi.responses import JSONResponse
from openai import models
from helpers.config import Settings, get_settings
from controllers import DataController,ProjectController,ProcessController
import aiofiles 
import logging
import aiofiles
import os
from  models import ResponseStatus
from .schemes.data import processRequest
logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["Data Routes"]
)
@data_router.post("/upload/{project_id}")
async def upload_data(project_id: str,file: UploadFile, app_settings: Settings = Depends(get_settings)):
    
    is_valid, status_message = await DataController().validate_uploaded_file(file=file)
    print(is_valid, status_message)
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": status_message})
    project_dir_path= ProjectController().get_project_files_path(project_id=project_id)
    file_path,file_id = DataController().generate_unique_file_Path(orig_file_name=file.filename,project_id=project_id)
    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            while chunk:= await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
             await out_file.write(chunk)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": ResponseStatus.FILE_UPLOAD_SUCCESS.value,"file_id":file_id})
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": ResponseStatus.FILE_UPLOAD_FAILED.value})

@data_router.post("/process/{project_id}")
async def process_endpoint(project_id:str,process_request:processRequest):
    file_id=process_request.file_id
    chunk_size=process_request.chunk_size
    overlap_size=process_request.overlap_size
    process_controller=ProcessController(project_id=project_id)
    file_content=process_controller.get_file_content(file_id=file_id)
    file_chunks=  process_controller.process_file_content(file_contant=file_content,
                                                         file_id=file_id,chunk_size=chunk_size,
                                                         overlap_size=overlap_size)


    if file_content is None or len(file_content)==0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": ResponseStatus.FILE_NOT_FOUND.value})
    return file_chunks
    
