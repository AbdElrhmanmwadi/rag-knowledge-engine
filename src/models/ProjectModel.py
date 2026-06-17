from sqlalchemy import func, select

from models.db_schemes.minirag.scheme import Project

from .BaseDataModle import BaseDataModel
from .enums.DatabaseEunm import DataBaseEnum
class ProjectModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.db_client=db_client

    @classmethod
    async def create_instance(cls,db_client)  :
        instance= cls(db_client)
     #   await instance.init_collection()
        return instance

    async def create_project(self, project: Project):
        async with self.db_client() as session:
            session.add(project)
            await session.commit()
            await session.refresh(project)
            return project
        
    async def get_project_by_id(self, project_id: str):
        try:
            project_id_int = int(project_id)
        except (TypeError, ValueError) as e:
            raise ValueError(f"project_id must be an integer string, got: {project_id!r}") from e

        async with self.db_client() as session:
            query = select(Project).where(Project.project_id == project_id_int)
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def get_project_or_create(self, project_id: str, owner_id: int):
        try:
            project_id_int = int(project_id)
        except (TypeError, ValueError) as e:
            raise ValueError(f"project_id must be an integer string, got: {project_id!r}") from e

        async with self.db_client() as session:
            query = select(Project).where(Project.project_id == project_id_int)
            result = await session.execute(query)

            project_obj = result.scalar_one_or_none()

            if project_obj is None:
                new_project = Project(project_id=project_id_int, owner_id=owner_id)
                session.add(new_project)
                await session.commit()
                await session.refresh(new_project)
                return new_project

            return project_obj
        
    async def get_projects_for_owner(self, owner_id: int, page: int = 1, page_size: int = 50):
        async with self.db_client() as session:
            total_query = (
                select(func.count(Project.project_id))
                .where(Project.owner_id == owner_id)
            )
            total_documents = (await session.execute(total_query)).scalar_one()
            total_pages = total_documents // page_size
            if total_documents % page_size > 0:
                total_pages += 1
            query = (
                select(Project)
                .where(Project.owner_id == owner_id)
                .order_by(Project.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(query)
            projects = result.scalars().all()
            return projects, total_pages, total_documents

    async def get_all_projects(self,page:int=1,page_size:int=10):
        async with self.db_client() as session:
            async with session.begin():
                total_query=select(func.count(Project.project_id))
                total_result= await session.execute(total_query)
                total_documents=total_result.scalar_one()
                total_page=total_documents// page_size
                if total_documents% page_size>0:
                    total_page +=1
                query=select(Project).offset((page-1)*page_size).limit(page_size)
                result = await session.execute(query)
                projects = result.scalars().all()
                return projects,total_page
    async def delete_project_by_id(self, project_id: str):
        try:
            project_id_int = int(project_id)
        except (TypeError, ValueError) as e:
            raise ValueError(f"project_id must be an integer string, got: {project_id!r}") from e

        async with self.db_client() as session:
            query = select(Project).where(Project.project_id == project_id_int)
            result = await session.execute(query)

            project_obj = result.scalar_one_or_none()

            if project_obj is not None:
                await session.delete(project_obj)
                await session.commit()

            return project_obj
            
        
