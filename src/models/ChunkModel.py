from sqlalchemy import func, select

from models.db_schemes.minirag.scheme import DataChunk

from .BaseDataModle import BaseDataModel
from .enums.DatabaseEunm import DataBaseEnum
class ChunkModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.db_client=db_client

    @classmethod
    async def create_instance(cls,db_client)  :
        instance= cls(db_client)
     #   await instance.init_collection()
        return instance

    async def create_chunk(self, chunk: DataChunk):
        async with self.db_client() as session:
            async with session.begin():
                session.add(chunk)
                await session.commit()
                await session.refresh(chunk)
        return chunk
       
    async def get_chunk(self, chunk_id: str):
        async with self.db_client() as session:
            async with session.begin():
                query = select(DataChunk).where(DataChunk.chunk_id == chunk_id)
                result = await session.execute(query)
                chunk = result.scalar_one_or_none()
            return chunk
        
    async def insert_many_chunks(self,chunks:list, batch_size:int=100):
        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    session.add_all(batch)
        return len(chunks)
    
    async def delete_chunks_by_project_id(self, project_id: str):
        async with self.db_client() as session:
            async with session.begin():
                query = select(DataChunk).where(DataChunk.chunk_project_id == project_id)
                result = await session.execute(query)
                chunks_to_delete = result.scalars().all()
                for chunk in chunks_to_delete:
                    await session.delete(chunk)
                await session.commit()
        return len(chunks_to_delete)
    
    async def get_chunks_by_project_id(self, project_id: str,page_number:int=1,page_size:int=10):
        async with self.db_client() as session:
            async with session.begin():
                query = select(DataChunk).where(DataChunk.chunk_project_id == project_id).offset((page_number-1)*page_size).limit(page_size)
                result = await session.execute(query)
                chunks = result.scalars().all()
            return chunks
    async def get_chunks_count_by_project_id(self, project_id):
        count = 0
        async with self.db_client() as session:
            async with session.begin():
                query = select(func.count(DataChunk.chunk_id)).where(DataChunk.chunk_project_id == project_id)
                result = await session.execute(query)
                count = result.scalar()
            return count
