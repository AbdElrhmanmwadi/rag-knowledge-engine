import shutil

from fastapi import APIRouter, Depends, Request, UploadFile, status
from fastapi.responses import JSONResponse
from helpers.config import Settings, get_settings
from helpers.auth_dependencies import get_current_user
from helpers.db import get_db
from helpers.process_reset import reset_project_processing_state
from controllers import DataController, ProjectController, ProcessController
import aiofiles
import logging
import os
from models import ResponseStatus
from routes.schemes.data import processRequest
from models.ProjectModel import ProjectModel
from models.AssetModel import AssetModel
from models.ChunkModel import ChunkModel
from models.user_model import User
from models.db_schemes.minirag.scheme import Asset
from models.db_schemes.minirag.scheme import DataChunk
from models.enums.AssetTypeEnum import AssetTypeEnum
from controllers.NLPController import NLPController
from services.project_access import get_project_for_user
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["Data Routes"]
)


@data_router.post("/upload/{project_id}")
async def upload_data(
    request: Request,
    project_id: int,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    app_settings: Settings = Depends(get_settings),
):
    project = await get_project_for_user(
        db, project_id=project_id, user_id=current_user.id, create_if_missing=True
    )
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)

    is_valid, status_message = await DataController().validate_uploaded_file(file=file)
    print(is_valid, status_message)
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": status_message})
    file_path, file_id = DataController().generate_unique_file_Path(
        orig_file_name=file.filename, project_id=str(project_id)
    )
    try:
        async with aiofiles.open(file_path, "wb") as out_file:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await out_file.write(chunk)
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": ResponseStatus.FILE_UPLOAD_FAILED.value},
        )
    asset_resource = Asset(
        asset_project_id=project.project_id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=file_id,
        asset_size=os.path.getsize(file_path),
    )
    await asset_model.create_asset(asset=asset_resource)
    return JSONResponse(
        content={
            "signal": ResponseStatus.FILE_UPLOAD_SUCCESS.value,
            "file_id": file_id,
        }
    )


@data_router.post("/process/{project_id}")
async def process_endpoint(
    request: Request,
    project_id: int,
    process_request: processRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset
    project = await get_project_for_user(
        db, project_id=project_id, user_id=current_user.id, create_if_missing=True
    )
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    nlp_Controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        embedding_client=request.app.embedding_client,
        generation_client=request.app.generation_client,
        template_parser=request.app.template_parser,
    )

    project_file_ids = {}

    if process_request.file_id:
        asset_record = await asset_model.get_asset_record(
            asset_project_id=project.project_id,
            asset_name=process_request.file_id,
        )
        if asset_record is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseStatus.FILE_ID_ERROR.value,
                },
            )
        project_file_ids = {
            asset_record.asset_id: asset_record.asset_name
        }

    else:
        project_file = await asset_model.get_all_project_asset(
            asset_project_id=project.project_id, asset_type=AssetTypeEnum.FILE.value
        )
        project_file_ids = {
            record.asset_id: record.asset_name
            for record in project_file
        }
    if len(project_file_ids) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseStatus.NO_FILES_ERROR.value,
            },
        )

    process_controller = ProcessController(project_id=str(project_id))
    no_records = 0
    no_files = 0
    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)
    if do_reset == 1:
        _ = await reset_project_processing_state(
            chunk_model=chunk_model,
            vectordb_client=request.app.vectordb_client,
            collection_name=nlp_Controller.create_collection_name(project_id=project.project_id),
            project_id=project.project_id,
        )

    for asset_id, file_id in project_file_ids.items():
        file_content = process_controller.get_file_content(file_id=file_id)
        if file_content is None:
            logger.error(f"error while process file_id{file_id}")
            continue
        file_chunks = process_controller.process_file_content(
            file_contant=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
        )
        if file_chunks is None or len(file_chunks) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseStatus.FILE_PROCESS_FAILED.value,
                },
            )

        if file_content is None or len(file_content) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"status": ResponseStatus.FILE_NOT_FOUND.value},
            )

        file_chunks_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i + 1,
                chunk_project_id=project.project_id,
                chunk_asset_id=asset_id,
            )
            for i, chunk in enumerate(file_chunks)
        ]

        no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records)
        no_files += 1

    return JSONResponse(
        content={
            "signal": ResponseStatus.FILE_PROCESS_SUCCESS.value,
            "inserted_chunks": no_records,
            "processed_files": no_files,
        }
    )


@data_router.get("/files/{project_id}")
async def list_files(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_for_user(
        db, project_id=project_id, user_id=current_user.id, create_if_missing=False
    )
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)

    project_files = await asset_model.get_all_project_asset(
        asset_project_id=project.project_id, asset_type=AssetTypeEnum.FILE.value
    )
    files_list = [
        {
            "file_id": record.asset_id,
            "file_size": record.asset_size,
            "file_name": record.asset_name,
            "file_type": record.asset_type,
            "file_created_at": record.created_at.isoformat() if getattr(record, "created_at", None) is not None else None,
            "file_updated_at": record.updated_at.isoformat() if getattr(record, "updated_at", None) is not None else None,
        }
        for record in project_files
    ]
    return JSONResponse(
        content={
            "signal": ResponseStatus.FILE_LIST_SUCCESS.value,
            "files": files_list,
        }
    )


@data_router.delete("/delete/{project_id}/{file_id}")
async def delete_file(
    request: Request,
    project_id: int,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_for_user(
        db, project_id=project_id, user_id=current_user.id, create_if_missing=False
    )
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    asset_record = await asset_model.get_asset_record(
        asset_project_id=project.project_id, asset_name=file_id
    )
    if asset_record is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseStatus.FILE_ID_ERROR.value,
            },
        )
    deleted_asset = await asset_model.delete_asset_by_id(asset_id=asset_record.asset_id)
    if deleted_asset is None:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "signal": ResponseStatus.FILE_PROCESS_FAILED.value,
            },
        )
    file_path = os.path.join(
        ProjectController().get_project_files_path(project_id=str(project_id)),
        file_id,
    )
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": ResponseStatus.FILE_PROCESS_FAILED.value},
        )

    return JSONResponse(
        content={
            "signal": ResponseStatus.FILE_PROCESS_SUCCESS.value,
            "deleted_file": file_id,
        }
    )


@data_router.delete("/delete_all/{project_id}")
async def delete_all_files(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_for_user(
        db, project_id=project_id, user_id=current_user.id, create_if_missing=False
    )
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.delete_project_by_id(project_id=str(project_id))
    if project is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseStatus.PROJECT_ID_ERROR.value,
            },
        )
    project_path = ProjectController().get_project_files_path(project_id=str(project_id))
    try:
        if os.path.exists(project_path):
            shutil.rmtree(project_path)
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": ResponseStatus.PROJECT_DELETE_FAILED.value},
        )

    return JSONResponse(
        content={
            "signal": ResponseStatus.PROJECT_DELETE_SUCCESS.value,
            "deleted_project": project_id,
        }
    )


@data_router.get("/file/{project_id}/{file_id}")
async def get_file_info(
    request: Request,
    project_id: int,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_for_user(
        db, project_id=project_id, user_id=current_user.id, create_if_missing=False
    )
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)

    asset_record = await asset_model.get_asset_record(
        asset_project_id=project.project_id,
        asset_name=file_id,
    )

    if asset_record is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "signal": ResponseStatus.FILE_ID_ERROR.value,
                "message": "File not found",
            },
        )

    file_path = os.path.join(
        ProjectController().get_project_files_path(project_id=str(project_id)),
        file_id,
    )

    file_exists = os.path.exists(file_path)

    file_size = None
    if file_exists:
        try:
            file_size = os.path.getsize(file_path)
        except Exception as e:
            logger.error(f"Error reading file size: {e}")

    return JSONResponse(
        content={
            "signal": ResponseStatus.FILE_LIST_SUCCESS.value,
            "file": {
                "file_id": asset_record.asset_name,
                "asset_id": asset_record.asset_id,
                "project_id": project.project_id,
                "file_size": file_size or asset_record.asset_size,
                "asset_type": asset_record.asset_type,
                "exists_on_disk": file_exists,
                "file_path": file_path if file_exists else None,
                "asset_config": asset_record.asset_config or {},
            },
        }
    )
