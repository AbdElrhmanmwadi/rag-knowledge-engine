from fastapi import FastAPI,Depends,APIRouter, UploadFile,status,Request
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
from models.ProjectModel import ProjectModel
from models.AssetModel import AssetModel


from models.ChunkModel import ChunkModel
from models.db_schemes.minirag.scheme import DataChunk
from models.db_schemes.minirag.scheme import Asset
from models.enums import ResponseEnums,AssetTypeEnum
logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["Data Routes"]
)
@data_router.post("/upload/{project_id}")
async def upload_data(request: Request, project_id: int, file: UploadFile, app_settings: Settings = Depends(get_settings)):
    project_model= await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=str(project_id))
    asset_model=await AssetModel.create_instance(db_client=request.app.db_client)
   
    is_valid, status_message = await DataController().validate_uploaded_file(file=file)
    print(is_valid, status_message)
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": status_message})
    project_dir_path= ProjectController().get_project_files_path(project_id=str(project_id))
    file_path,file_id = DataController().generate_unique_file_Path(orig_file_name=file.filename,project_id=str(project_id))
    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            while chunk:= await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
             await out_file.write(chunk)
        # return JSONResponse(status_code=status.HTTP_200_OK, content={"status": ResponseStatus.FILE_UPLOAD_SUCCESS.value,"file_id":file_id,"project_id":project.project_id})
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": ResponseStatus.FILE_UPLOAD_FAILED.value})
    asset_resource = Asset(
        asset_project_id=project.project_id,
        asset_type=file.content_type,
        asset_name=file_id,
        asset_size=os.path.getsize(file_path)
    )
    asset_record=await asset_model.create_asset(asset=asset_resource)
    return JSONResponse(
        content={
            "signal": ResponseStatus.FILE_UPLOAD_SUCCESS.value,
            "file_id": file_id,
        }
    )


@data_router.post("/process/{project_id}")
async def process_endpoint(request:Request,project_id: int, process_request: processRequest):
    file_id=process_request.file_id
    chunk_size=process_request.chunk_size
    overlap_size=process_request.overlap_size
    project_model= await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=str(project_id))
    asset_model=await AssetModel.create_instance(db_client=request.app.db_client)

    no_records = 0
    no_files = 0
    process_controller=ProcessController(project_id=str(project_id))
    file_content=process_controller.get_file_content(file_id=file_id)
    file_chunks=  process_controller.process_file_content(file_contant=file_content,
                                                         file_id=file_id,chunk_size=chunk_size,
                                                         overlap_size=overlap_size)

    chunk_model = await ChunkModel.create_instance(
        db_client=request.app.db_client
    )
    
    


    if file_content is None or len(file_content)==0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": ResponseStatus.FILE_NOT_FOUND.value})
    
    asset_record=await asset_model.get_asset_record(asset_project_id=project.project_id, asset_name=process_request.file_id)
    file_chunks_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i+1,
                chunk_project_id=project.project_id,
                chunk_asset_id=asset_record.asset_id
            )
            for i, chunk in enumerate(file_chunks) 
        ]

    no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records)
    no_files += 1

    return JSONResponse(
        content={
            "signal": ResponseStatus.FILE_PROCESS_FAILED.value,
            "inserted_chunks": no_records,
            "processed_files": no_files
        }
    )
    
