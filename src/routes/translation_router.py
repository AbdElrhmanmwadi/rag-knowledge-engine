from fastapi import APIRouter, BackgroundTasks, Request, status
from fastapi.responses import FileResponse, JSONResponse

from controllers import TranslationController
from models.enums.ResponseEnums import ResponseStatus
from routes.schemes.translation import TranslationFileRequest


translation_router = APIRouter(
    prefix="/translate",
    tags=["Translation"]
)


@translation_router.post("/file")
async def translate_file(request: Request, background_tasks: BackgroundTasks, translation_request: TranslationFileRequest):
    translation_controller = TranslationController(
        db_client=request.app.db_client,
        translation_provider=request.app.translation_provider
    )
    translation_job, error_message = await translation_controller.create_translation_job(
        project_id=translation_request.project_id,
        file_id=translation_request.file_id,
        source_lang=translation_request.source_lang,
        target_lang=translation_request.target_lang
    )
    if translation_job is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "signal": ResponseStatus.TRANSLATION_FAILED.value,
                "message": error_message or "Translation job could not be created"
            }
        )

    background_tasks.add_task(translation_controller.process_translation_job, translation_job.job_id)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "signal": ResponseStatus.TRANSLATION_JOB_CREATED.value,
            "job_id": translation_job.job_id,
            "status": translation_job.status,
            "asset_id": translation_job.asset_id,
            "source_lang": translation_job.source_lang,
            "target_lang": translation_job.target_lang
        }
    )


@translation_router.get("/status/{job_id}")
async def get_translation_status(request: Request, job_id: int):
    translation_controller = TranslationController(
        db_client=request.app.db_client,
        translation_provider=request.app.translation_provider
    )
    translation_job_status = await translation_controller.get_translation_job_status(job_id=job_id)
    if translation_job_status is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "signal": ResponseStatus.TRANSLATION_FAILED.value,
                "message": "Translation job was not found"
            }
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseStatus.TRANSLATION_STATUS_SUCCESS.value,
            "job": translation_job_status
        }
    )


@translation_router.get("/download/{job_id}")
async def download_translated_file(request: Request, job_id: int):
    translation_controller = TranslationController(
        db_client=request.app.db_client,
        translation_provider=request.app.translation_provider
    )
    download_payload, error_message, response_status = await translation_controller.get_translation_download(job_id=job_id)
    if download_payload is None:
        return JSONResponse(
            status_code=response_status,
            content={
                "signal": ResponseStatus.TRANSLATION_FAILED.value,
                "message": error_message
            }
        )

    return FileResponse(
        path=download_payload["file_path"],
        filename=download_payload["download_name"],
        media_type="application/octet-stream"
    )
