import os

from fastapi import status
from stores.translation.TranslationExceptions import TranslationException
from models.AssetModel import AssetModel
from models.ProjectModel import ProjectModel
from models.TranslationJobModel import TranslationJobModel
from models.db_schemes.minirag.scheme import Asset, TranslationJob
from models.enums.AssetTypeEnum import AssetTypeEnum
from .BaseController import BaseController
from .DataController import DataController
from .ProjectController import ProjectController


class TranslationController(BaseController):
    def __init__(self, db_client, translation_provider):
        super().__init__()
        self.db_client = db_client
        self.translation_provider = translation_provider

    async def create_translation_job(
        self,
        project_id: int,
        file_id: str,
        source_lang: str = None,
        target_lang: str = None
    ):
        project_model = await ProjectModel.create_instance(db_client=self.db_client)
        asset_model = await AssetModel.create_instance(db_client=self.db_client)
        translation_job_model = await TranslationJobModel.create_instance(db_client=self.db_client)

        project = await project_model.get_project_by_id(project_id=str(project_id))
        if project is None:
            return None, "Project was not found"
        source_asset = await asset_model.get_asset_record(
            asset_project_id=project.project_id,
            asset_name=file_id
        )
        if source_asset is None:
            return None, "Source file was not found for this project"

        translation_job = TranslationJob(
            project_id=project.project_id,
            asset_id=source_asset.asset_id,
            source_lang=(source_lang or "auto"),
            target_lang=target_lang or self.app_settings.DEFAULT_TARGET_LANG,
            status="pending"
        )
        translation_job = await translation_job_model.create_job(translation_job=translation_job)
        return translation_job, None

    async def process_translation_job(self, job_id: int):
        translation_job_model = await TranslationJobModel.create_instance(db_client=self.db_client)
        asset_model = await AssetModel.create_instance(db_client=self.db_client)

        translation_job = await translation_job_model.update_job(job_id=job_id, status="processing", error_message=None)
        if translation_job is None:
            return None

        try:
            source_asset = await asset_model.get_asset_by_id(asset_id=translation_job.asset_id)
            if source_asset is None:
                raise ValueError("Source asset was not found")

            source_file_path = self._build_project_file_path(
                project_id=translation_job.project_id,
                file_name=source_asset.asset_name
            )
            
            # Read source file as bytes
            with open(source_file_path, "rb") as f:
                file_bytes = f.read()

            # Translate file directly using translation provider
            translated_file_bytes = await self.translation_provider.translate_file(
                file_bytes=file_bytes,
                filename=source_asset.asset_name,
                source_lang=translation_job.source_lang,
                target_lang=translation_job.target_lang
            )

            # Build output file path and save translated file
            translated_file_name = self._build_translated_file_name(
                source_file_name=source_asset.asset_name,
                target_lang=translation_job.target_lang
            )
            translated_file_path, stored_file_name = DataController().generate_unique_file_Path(
                orig_file_name=translated_file_name,
                project_id=str(translation_job.project_id)
            )
            
            with open(translated_file_path, "wb") as f:
                f.write(translated_file_bytes)

            translated_asset = Asset(
                asset_project_id=translation_job.project_id,
                asset_type=AssetTypeEnum.TRANSLATED_FILE.value,
                asset_name=stored_file_name,
                asset_size=os.path.getsize(translated_file_path),
                asset_config={
                    "source_asset_id": source_asset.asset_id,
                    "translation_job_id": translation_job.job_id,
                    "source_lang": translation_job.source_lang,
                    "target_lang": translation_job.target_lang,
                    "download_name": translated_file_name
                }
            )
            translated_asset = await asset_model.create_asset(asset=translated_asset)

            await translation_job_model.update_job(
                job_id=job_id,
                status="completed",
                result_asset_id=translated_asset.asset_id,
                error_message=None
            )
            return translated_asset
        except TranslationException as exc:
            # Translation-specific error: extract api_error_code and message
            error_msg = f"{exc.message} (code: {exc.api_error_code})" if exc.api_error_code else exc.message
            await translation_job_model.update_job(
                job_id=job_id,
                status="failed",
                error_message=error_msg
            )
            return None
        except Exception as exc:
            # Other errors (file I/O, database, etc.)
            await translation_job_model.update_job(
                job_id=job_id,
                status="failed",
                error_message=str(exc)
            )
            return None

    async def get_translation_job_status(self, job_id: int):
        translation_job_model = await TranslationJobModel.create_instance(db_client=self.db_client)
        asset_model = await AssetModel.create_instance(db_client=self.db_client)

        translation_job = await translation_job_model.get_job(job_id=job_id)
        if translation_job is None:
            return None

        result_asset = None
        if translation_job.result_asset_id is not None:
            result_asset = await asset_model.get_asset_by_id(asset_id=translation_job.result_asset_id)

        return {
            "job_id": translation_job.job_id,
            "asset_id": translation_job.asset_id,
            "source_lang": translation_job.source_lang,
            "target_lang": translation_job.target_lang,
            "status": translation_job.status,
            "result_asset_id": translation_job.result_asset_id,
            "result_file_id": result_asset.asset_name if result_asset else None,
            "download_url": f"/translate/download/{translation_job.job_id}" if result_asset else None,
            "error_message": translation_job.error_message
        }

    async def get_translation_download(self, job_id: int):
        translation_job_model = await TranslationJobModel.create_instance(db_client=self.db_client)
        asset_model = await AssetModel.create_instance(db_client=self.db_client)

        translation_job = await translation_job_model.get_job(job_id=job_id)
        if translation_job is None:
            return None, "Translation job was not found", status.HTTP_404_NOT_FOUND

        if translation_job.status != "completed" or translation_job.result_asset_id is None:
            return None, "Translated file is not ready for download yet", status.HTTP_409_CONFLICT

        translated_asset = await asset_model.get_asset_by_id(asset_id=translation_job.result_asset_id)
        if translated_asset is None:
            return None, "Translated file asset was not found", status.HTTP_404_NOT_FOUND

        translated_file_path = self._build_project_file_path(
            project_id=translation_job.project_id,
            file_name=translated_asset.asset_name
        )
        if not os.path.exists(translated_file_path):
            return None, "Translated file was not found on disk", status.HTTP_404_NOT_FOUND

        asset_config = translated_asset.asset_config or {}
        download_name = asset_config.get("download_name") or translated_asset.asset_name

        return {
            "file_path": translated_file_path,
            "download_name": download_name
        }, None, status.HTTP_200_OK

    def _build_project_file_path(self, project_id: int, file_name: str):
        project_files_path = ProjectController().get_project_files_path(project_id=str(project_id))
        return os.path.join(project_files_path, file_name)

    def _build_translated_file_name(self, source_file_name: str, target_lang: str):
        file_root, file_extension = os.path.splitext(source_file_name)
        language_suffix = self._sanitize_file_name_part(target_lang or self.app_settings.DEFAULT_TARGET_LANG)
        return f"{file_root}_{language_suffix}_translated{file_extension}"

    def _sanitize_file_name_part(self, value: str):
        sanitized_value = "".join(
            char if char.isascii() and (char.isalnum() or char in ("_", "-")) else "_"
            for char in str(value or "").strip().lower()
        )
        return sanitized_value.strip("_") or "translated"
    
