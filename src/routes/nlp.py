from fastapi import FastAPI,APIRouter,status,Request
from fastapi.responses import JSONResponse
import logging

from controllers import NLPController
from models.ChunkModel import ChunkModel
from models.enums.ResponseEnums import ResponseStatus
from routes.schemes.nlp import PushRequest,searchRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

nlp_router=APIRouter(
    prefix="/api/v1/nlp",
    tags=["api-v1","nlp"]
)
@nlp_router.post("/index/push/{project_id}")
async def index_project(request:Request,project_id:int,Push_Request:PushRequest):
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
        generation_client=request.app.generation_client,
        template_parser=request.app.template_parser
    )
    has_record=True
    page_no=1
    inserted_items_count=0

    _=await request.app.vectordb_client.create_collection(
        collection_name=nlp_controller.create_collection_name(project_id=project.project_id),
        embedding_size=request.app.embedding_client.embedding_size,
        do_reset=Push_Request.do_reset) 
    

    #batch
    total_chunks_count= await chunk_model.get_chunks_count_by_project_id(project_id=project.project_id)
    bar=tqdm(total=total_chunks_count,desc="Indexing chunks into vector database",position=0)


    if total_chunks_count==0:
        has_record=False
    




    with logging_redirect_tqdm():
        while has_record:
            page_chunks=await chunk_model.get_chunks_by_project_id(
            project_id=project.project_id,page_number=page_no)
            is_first_page = (page_no == 1)
            if not page_chunks or len(page_chunks)==0:
                has_record=False
                break
            is_inserted =await nlp_controller.index_into_vectordb(project=project,chunks=page_chunks,do_reset=is_first_page)
            if not is_inserted:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "signal": ResponseStatus.INSERT_INTO_VECTORDB_ERROR.value
                    }
                )
            bar.update(len(page_chunks))
            inserted_items_count +=len(page_chunks)
            page_no += 1 

        # Create vector index once after all data is inserted
        collection_name = nlp_controller.create_collection_name(project_id=project.project_id)
        await request.app.vectordb_client.create_vector_index(collection_name=collection_name)
        bar.close()
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.INSERT_INTO_VECTORDB_SUCCESS.value
        }
    )
@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request:Request,project_id:int):
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )
    project= await project_model.get_project_or_create(
        project_id=project_id
    )
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
        generation_client=request.app.generation_client,
        template_parser=request.app.template_parser
    )
    collection_info= await nlp_controller.get_vectordb_collection_info(project=project)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.GET_VECTORDB_COLLECTION_INFO_SUCCESS.value,
            "collection_info":collection_info
        }
    )
@nlp_router.post("/index/search/{project_id}")
async def search_project_index(request:Request,project_id:int,search_request:searchRequest):
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )
    project= await project_model.get_project_or_create(
        project_id=project_id
    )
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
        generation_client=request.app.generation_client,
        template_parser=request.app.template_parser
    )
    search_result=await nlp_controller.search_in_vectordb(project=project,text=search_request.text,limit=search_request.limit)
    if search_result is False:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseStatus.VECTOR_SEARCH_FAILED.value
            }
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.VECTOR_SEARCH_SUCCESS.value,
            "search_result":[
                {
                    "text":result.text,
                    "score":result.score,
                    "meta_data":result.meta_data
                }
                for result in search_result
            ]
        }
    )
@nlp_router.post("/index/answer/{project_id}")
async def answer_rag_question(request:Request,project_id:int,search_request:searchRequest):
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )
    project= await project_model.get_project_or_create(
        project_id=project_id
    )
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
        generation_client=request.app.generation_client,
        template_parser=request.app.template_parser
    )
    
    rag_answer,full_prompt,chat_history= await nlp_controller.answer_rag_question(query=search_request.text,project=project,limit=search_request.limit)
    if not rag_answer:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,content={"signal":ResponseStatus.RAG_ANSWER_FAILED.value,"message":"No answer could be generated from the retrieved documents"})
    return JSONResponse(status_code=status.HTTP_200_OK,content={"signal":ResponseStatus.RAG_ANSWER_SUCCESS.value,
                                 "answer": rag_answer,
                                 "full_prompt": full_prompt,
                                 "chat_history": chat_history})



