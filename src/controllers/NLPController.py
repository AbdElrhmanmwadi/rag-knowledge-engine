import asyncio
import os
from typing import List

from models.db_schemes.minirag.scheme.project import Project
from models.db_schemes.minirag.scheme.data_chunk import DataChunk
from stores.LLMEnum import DocumentTypeEnum

from .BaseController import BaseController
import json
import logging

logger = logging.getLogger(__name__)

class NLPController(BaseController):
    def __init__(self,vectordb_client,embedding_client,generation_client,template_parser):
        super().__init__()
        self.vectordb_client = vectordb_client
        self.embedding_client = embedding_client
        self.generation_client = generation_client
        self.template_parser = template_parser
    def create_collection_name(self,project_id:str):
            return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()

    async def reset_vector_db_collection(self,project:Project):
            collection_name = self.create_collection_name(project_id= project.project_id)
            
            return  await self.vectordb_client.delete_collection(collection_name=collection_name)    
    async def get_vectordb_collection_info(self,project:Project):
            collection_name = self.create_collection_name(project_id= project.project_id)
            collection_info =  await self.vectordb_client.get_collection_info(collection_name=collection_name)

            return  json.loads(json.dumps(collection_info, default=lambda x: x.__dict__))    
    async def index_into_vectordb(self,project:Project,chunks:List[DataChunk],do_reset:bool=False):
            collection_name = self.create_collection_name(project_id= project.project_id)
            texts=[c.chunk_text for c in chunks]
            metadata=[c.chunk_metadata for c in chunks]
            record_ids=[c.chunk_id for c in chunks]  # Extract integer chunk_ids
            # all text will be embedded once
            vectors=self.embedding_client.embed_text(text=texts,document_type=DocumentTypeEnum.DOCUMENT.value)
            # embedding text one by one 

            # vectors=[
            #     self.embedding_client.embed_text(text=text,document_type=DocumentTypeEnum.DOCUMENT.value)
            #     for text in texts
            # ]
            _= await self.vectordb_client.create_collection(collection_name=collection_name,embedding_size=self.embedding_client.embedding_size,do_reset=do_reset)

            _= await self.vectordb_client.insert_many(collection_name=collection_name,
                                            texts=texts,vectors=vectors,metadata=metadata,record_ids=record_ids)
            return True
    async def search_in_vectordb(self,project:Project,text:str,limit:int):
            collection_name = self.create_collection_name(project_id= project.project_id)
            vectors=self.embedding_client.embed_text(text=text,document_type=DocumentTypeEnum.QUERY.value)
            query_vector=None
            
            if not vectors or len(vectors)==0:
                return False
            if isinstance(vectors,list) and len(vectors)>0:
                query_vector=vectors[0]
            if query_vector is None:
                return False
            search_results=await self.vectordb_client.search_by_vector(collection_name=collection_name,
                                                                       vector=query_vector ,
                                                                       limit=limit)
            if search_results is None:
                return False
            return search_results
    def _build_history_messages(self, history):
        """Convert a neutral [{'role','content'}] history into provider-formatted messages.

        Roles other than user/assistant (and empty content) are skipped. The final
        user query is appended later by the generation client, so it is not added here.
        """
        if not history:
            return []
        enums = self.generation_client.enums
        role_map = {
            "user": enums.USER.value,
            "assistant": enums.ASSISTANT.value,
        }
        messages = []
        for turn in history:
            role = role_map.get((turn.get("role") or "").lower())
            content = (turn.get("content") or "").strip()
            if not role or not content:
                continue
            messages.append(
                self.generation_client.constract_prompt(prompt=content, role=role)
            )
        return messages

    async def answer_rag_question(self,query:str,project:Project,limit:int=30,history:list=None):
        answer = None
        full_prompt = None
        chat_history = None
        retreved_documant= await self.search_in_vectordb(project=project,text=query,limit=limit)
        if not retreved_documant or len(retreved_documant)==0:
            logger.warning(f"No documents retrieved for query: {query}")
            return answer,full_prompt,chat_history
        logger.info(f"Retrieved {len(retreved_documant)} documents")
        system_promit=self.template_parser.get("rag","system_prompt")
        if not system_promit:
            logger.error("Failed to get system_prompt from template parser")
            return answer,full_prompt,chat_history
        document_prompts = []
        for idx, doc in enumerate(retreved_documant):
            doc_prompt = self.template_parser.get("rag","documant_prompt",{
                 "doc_number":idx+1,
                 "chunk_text":self.generation_client.process_text(doc.text),
                 "page_number":doc.meta_data.get("page") if doc.meta_data else None,
                 })
            if doc_prompt:
                document_prompts.append(doc_prompt)
        if not document_prompts:
            logger.error("Failed to generate document prompts")
            return answer,full_prompt,chat_history
        document_prompt="\n".join(document_prompts)
        footer_prompt=self.template_parser.get("rag","footer_prompt",{
            "query":query
        })
        if not footer_prompt:
            logger.error("Failed to get footer_prompt from template parser")
            return answer,full_prompt,chat_history
        chat_history=[
        self.generation_client.constract_prompt(prompt=system_promit,role=self.generation_client.enums.SYSTEM.value),]
        chat_history.extend(self._build_history_messages(history))
        full_prompt="\n\n".join([document_prompt, footer_prompt])
        logger.info(f"Generated full prompt with {len(document_prompts)} documents")
        try:
            answer = self.generation_client.genarate_text(
                prompt=full_prompt,
                chat_history=chat_history,
                max_output_tokens=None
            )
        except Exception as e:
            logger.error(f"Error generating text: {str(e)}")
            answer = None
        return answer,full_prompt,chat_history
 