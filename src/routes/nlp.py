from fastapi import FastAPI,APIRouter,status,Request
from fastapi.responses import JSONResponse
import logging
from controllers import NLPController
from models.ChunkModel import ChunkModel
from models.enums.ResponseEnums import ResponseStatus
from routes.schemes.nlp import PushRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel

nlp_router=APIRouter(
    prefix="/api/v1/nlp",
    tags=["api-v1","nlp"]
)
@nlp_router.post("/index/push/{project_id}")
async def get_project_index_info(request:Request,project_id:int,Push_Request:PushRequest):
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )
    project= await project_model.get_project_or_create(
        project_id=project_id
    )
    chunk_model=await ChunkModel.create_instance(
        db_client=request.app.db_client )
    
    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "signal": ResponseStatus.PROJECT_NOT_FOUND.value
            }
        )
    
    nlp_controller=NLPController(
        embedding_client=request.app.embedding_client,
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client
    )
    has_record=True
    page_no=1
    inserted_items_count=0
    while has_record:
        page_chunks=await chunk_model.get_chunks_by_project_id(
        project_id=project.project_id,page_number=page_no)
        if len(page_chunks):
            page_no+=1
        if not page_chunks or len(page_chunks)==0:
            has_record=False
            break
        is_inserted = nlp_controller.index_into_vectordb(project=project,chunks=page_chunks,do_reset=(page_no==1))
        if not is_inserted:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseStatus.INSERT_INTO_VECTORDB_ERROR.value
                }
            )
        inserted_items_count +=len(page_chunks)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.INSERT_INTO_VECTORDB_SUCCESS.value
        }
    )

      
    
  


