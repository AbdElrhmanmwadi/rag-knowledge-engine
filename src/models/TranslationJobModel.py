from sqlalchemy import select

from models.db_schemes.minirag.scheme import TranslationJob

from .BaseDataModle import BaseDataModel


class TranslationJobModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client):
        instance = cls(db_client)
        return instance

    async def create_job(self, translation_job: TranslationJob):
        async with self.db_client() as session:
            async with session.begin():
                session.add(translation_job)
                await session.flush()
                await session.refresh(translation_job)
        return translation_job

    async def get_job(self, job_id: int):
        async with self.db_client() as session:
            result = await session.execute(
                select(TranslationJob).where(TranslationJob.job_id == job_id)
            )
            translation_job = result.scalar_one_or_none()
            return translation_job

    async def update_job(self, job_id: int, **fields):
        async with self.db_client() as session:
            async with session.begin():
                result = await session.execute(
                    select(TranslationJob).where(TranslationJob.job_id == job_id)
                )
                translation_job = result.scalar_one_or_none()
                if translation_job is None:
                    return None
                for field_name, field_value in fields.items():
                    setattr(translation_job, field_name, field_value)
                await session.flush()
                await session.refresh(translation_job)
            return translation_job
