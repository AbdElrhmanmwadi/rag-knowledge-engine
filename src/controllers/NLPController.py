from typing import List

from models.db_schemes.minirag.scheme.project import Project
from models.db_schemes.minirag.scheme.data_chunk import DataChunk
from stores.LLMEnum import DocumentTypeEnum

from .BaseController import BaseController
import json

class NLPController(BaseController):
    def __init__(self,vectordb_client,embedding_client,generation_client,):
        super().__init__()
        self.vectordb_client = vectordb_client
        self.embedding_client = embedding_client
        self.generation_client = generation_client
    def create_collection_name(self,project_id:str):
            return f"collection_{project_id}".strip()

    def reset_vector_db_collection(self,project:Project):
            collection_name = self.create_collection_name(project_id= project.project_id)
            
            return self.vectordb_client.delete_collection(collection_name=collection_name)    
    def get_vectordb_collection_info(self,project:Project):
            collection_name = self.create_collection_name(project_id= project.project_id)
            collection_info =  self.vectordb_client.get_collection_info(collection_name=collection_name)

            return  json.loads(json.dumps(collection_info, default=lambda x: x.__dict__))    
    def index_into_vectordb(self,project:Project,chunks:List[DataChunk],do_reset:bool=False):
            collection_name = self.create_collection_name(project_id= project.project_id)
            texts=[c.chunk_text for c in chunks]
            metadata=[c.chunk_metadata for c in chunks]
            vectors=[
                self.embedding_client.embed_text(text=text,document_type=DocumentTypeEnum.DOCUMENT.value)
                for text in texts
            ]
            _=self.vectordb_client.create_collection(collection_name=collection_name,embedding_size=self.embedding_client.embedding_size,do_reset=do_reset)

            _=self.vectordb_client.insert_many(collection_name=collection_name,
                                            texts=texts,vectors=vectors,metadata=metadata)
            return True
               
            
