from unittest import result

from .BaseDataModle import BaseDataModel
from models.db_schemes.minirag.scheme import Asset
from sqlalchemy import select,func
class AssetModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.db_client=db_client
    @classmethod
    async def create_instance(cls,db_client):
        instance=cls(db_client)
        return instance
    async def create_asset(self,asset:Asset):
        async with self.db_client() as session:
            
                session.add(asset)
                await session.commit()
                await session.refresh(asset)
                
        return asset
    async def get_all_project_asset(self,asset_project_id:str ,asset_type:str):
        async with self.db_client() as session:
            async with session.begin():
                result=await session.execute(select(Asset).where(Asset.asset_project_id==asset_project_id,Asset.asset_type== asset_type))
                asset=result.scalars().all()
            return asset
    async def get_asset_record(self, asset_project_id:str,asset_name:str):
        async with self.db_client() as session:
            async with session.begin():
                result= await session.execute(select(Asset).where(Asset.asset_project_id==asset_project_id,Asset.asset_name==asset_name))
                asset=result.scalar_one_or_none()
            return asset
    async def get_asset_by_id(self, asset_id:int):
        async with self.db_client() as session:
            async with session.begin():
                result = await session.execute(select(Asset).where(Asset.asset_id == asset_id))
                asset = result.scalar_one_or_none()
            return asset
    

                
    

    
