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
from models.enums import ResponseEnums
from models.enums.AssetTypeEnum import AssetTypeEnum
from controllers.NLPController import NLPController
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
        asset_type=AssetTypeEnum.FILE.value,
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
    # file_id=process_request.file_id
    chunk_size=process_request.chunk_size
    overlap_size=process_request.overlap_size
    do_reset= process_request.do_reset
    project_model= await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=str(project_id))
    asset_model=await AssetModel.create_instance(db_client=request.app.db_client)
    nlp_Controller= NLPController(vectordb_client=request.app.vectordb_client,
                                embedding_client=request.app.embedding_client,
                                generation_client=request.app.generation_client,
                                template_parser=request.app.template_parser)

   
    project_file_ids={}

    if process_request.file_id :
        asset_record = await asset_model.get_asset_record(
            asset_project_id=project.project_id,
            asset_name=process_request.file_id
        )
        if asset_record is None:
                return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseStatus.FILE_ID_ERROR.value,
                }
            )
        project_file_ids = {
            asset_record.asset_id: asset_record.asset_name
        }

        
    else:
        project_file=await asset_model.get_all_project_asset(asset_project_id=project.project_id,asset_type=AssetTypeEnum.FILE.value)
        project_file_ids = {
            record.asset_id: record.asset_name 
            for record in project_file
        }
    if len(project_file_ids)==0:
         return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseStatus.NO_FILES_ERROR.value,
            }
        )

         
    process_controller=ProcessController(project_id=str(project_id))
    no_records = 0
    no_files = 0
    chunk_model = await ChunkModel.create_instance(
            db_client=request.app.db_client
        )
    if do_reset == 1:
        _ = await chunk_model.delete_chunks_by_project_id(
            project_id=project.project_id
        )
        _ = await request.app.vectordb_client.delete_collection(
            collection_name=nlp_Controller.create_collection_name(project_id=project.project_id)
        )


    asset_record=await asset_model.get_asset_record(asset_project_id=project.project_id, asset_name=process_request.file_id)


    for asset_id, file_id in project_file_ids.items():
        file_content=process_controller.get_file_content(file_id=file_id)
        if file_content is None :
            logger.error(f"error while process file_id{file_id}")
            continue
        file_chunks=  process_controller.process_file_content(file_contant=file_content,
                                                            file_id=file_id,chunk_size=chunk_size,
                                                            overlap_size=overlap_size)
        if file_chunks is None or len(file_chunks)==0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseStatus.FILE_PROCESS_FAILED.value,
                }
            )

        
        
        


        if file_content is None or len(file_content)==0:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": ResponseStatus.FILE_NOT_FOUND.value})
        
        
        file_chunks_records = [
                DataChunk(
                    chunk_text=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    chunk_order=i+1,
                    chunk_project_id=project.project_id,
                    chunk_asset_id=asset_id
                )
                for i, chunk in enumerate(file_chunks) 
            ]

        no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records)
        no_files += 1

    return JSONResponse(
        content={
            "signal": ResponseStatus.FILE_PROCESS_SUCCESS.value,
            "inserted_chunks": no_records,
            "processed_files": no_files
        }
    )
#endpoint to list files by project
@data_router.get("/files/{project_id}")
async def list_files(request:Request,project_id:int):
    project_model= await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=str(project_id))
    asset_model=await AssetModel.create_instance(db_client=request.app.db_client)
   
    project_files=await asset_model.get_all_project_asset(asset_project_id=project.project_id,asset_type=AssetTypeEnum.FILE.value)
    files_list=[
        {
            "file_id":record.asset_name,
            "file_size":record.asset_size
        }
        for record in project_files
    ]
    return JSONResponse(
        content={
            "signal": ResponseStatus.FILE_LIST_SUCCESS.value,
            "files": files_list
        }
    )



    
