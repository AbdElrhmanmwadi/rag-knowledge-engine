from typing import List
import uuid

from models.db_schemes.minirag.scheme.data_chunk import RetrievedDocument

from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import VectorDBEnums,DistanceMethodEnums
from qdrant_client import QdrantClient,models
import logging
class QdrantDBProvider(VectorDBInterface):
    def __init__(self,db_client:str,distance_method:str=None,default_vector_size:int=786,index_threshold: int=100):
        self.client=None
        self.db_client=db_client
        self.distance_method=None
        self.default_vector_size=default_vector_size
        self.index_threshold=index_threshold
        if distance_method==DistanceMethodEnums.COSINE.value:
            self.distance_method=models.Distance.COSINE
        elif distance_method==DistanceMethodEnums.DOT.value:
            self.distance_method=DistanceMethodEnums.DOT.value
        self.logger=logging.getLogger("uvicorn")

    async def connect(self):
        self.client=QdrantClient(path=self.db_client)
    async def disconnect(self):
        self.client= None
    async def is_collection_existed(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)
    async def list_all_collections(self) -> List:
        return self.client.get_collections()
    async def get_collection_info(self, collection_name: str) -> dict:
        return self.client.get_collection(collection_name=collection_name)
    async def delete_collection(self, collection_name: str):
        if await self.is_collection_existed(collection_name=collection_name):

            return self.client.delete_collection(collection_name=collection_name)
        



    async def create_collection(self, collection_name: str, 
                                embedding_size: int,
                                do_reset: bool = False):
        
        if do_reset :
           _ = self.delete_collection(collection_name=collection_name)
        if not self.is_collection_existed(collection_name=collection_name):   
            self.logger.info(f"creating new qudrant collection {collection_name} with embedding size {embedding_size} and distance method {self.distance_method}")
            _=await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method),
                    ) 
            return True
        # self.logger.error(f"collection {collection_name} already exists")
        return False

    
    async def insert_one(self, collection_name: str, text: str, vector: list,
                         metadata: dict = None, 
                         record_id: str = None):
        if not await self.is_collection_existed(collection_name=collection_name):
            self.logger.error(f"can not insert collection is not exist")
            return False
        try:
            record_id = record_id or str(uuid.uuid4())
            _ = self.client.upload_records(
                collection_name=collection_name,
                records=[
                    models.Record(
                        id=record_id,
                        vector=vector,
                        payload={
                            "text": text, "metadata": metadata
                        }
                    )
                ]
            )
        except Exception as e:
            self.logger.error(f"Error while inserting batch: {e}")
            return False
        
        return True

   
    async def insert_many(self, collection_name: str, texts: list, 
                          vectors: list, metadata: list = None, 
                          record_ids: list = None, batch_size: int = 50):
        
        if metadata is None:
            metadata = [None] * len(texts)

        if record_ids is None:
            record_ids = [str(uuid.uuid4()) for _ in texts]

        for i in range(0, len(texts), batch_size):
            batch_end = i + batch_size

            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]
            batch_ids = record_ids[i:batch_end]

            batch_records = [
                models.Record(
                    id=batch_ids[x] if batch_ids[x] is not None else str(uuid.uuid4()),
                    vector=batch_vectors[x],
                    payload={
                        "text": batch_texts[x], "metadata": batch_metadata[x]
                    }
                )

                for x in range(len(batch_texts))
            ]

            try:
                _ = self.client.upload_records(
                    collection_name=collection_name,
                    records=batch_records,
                )
            except Exception as e:
                self.logger.error(f"Error while inserting batch: {e}")
                return False

        return True

    
    async def search_by_vector(self, collection_name: str, vector: list, limit: int) ->list[RetrievedDocument]:
         results=self.client.search(collection_name=collection_name,query_vector=vector,limit=limit
                       )
         if not results or len(results)==0:
            return None
         return[
            RetrievedDocument(**{
                "text": result.payload["text"],
                "score": result.score
            })

            for result in results
        ]
    
        
        
        
        
    
        
    

