import asyncio
import logging
import os
import time
from typing import Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response

from controllers.NLPController import NLPController
from helpers.config import Settings, get_settings
from models.ProjectModel import ProjectModel
from models.enums.ResponseEnums import ResponseStatus
from routes.schemes.voice import TTSRequest


voice_router = APIRouter(
    prefix="/api/v1/voice",
    tags=["api-v1", "voice"],
)
logger = logging.getLogger("uvicorn.error")


@voice_router.post("/stt")
async def stt_endpoint(
    request: Request,
    audio: UploadFile = File(...),
    language: Optional[str] = None,
    app_settings: Settings = Depends(get_settings),
):
    voice = request.app.state.voice_controller
    audio_path = voice.unique_audio_path(
        project_id="tmp",
        suffix=os.path.splitext(audio.filename or "audio")[1] or ".bin",
    )
    try:
        read_started_at = time.perf_counter()
        async with aiofiles.open(audio_path, "wb") as out_file:
            while chunk := await audio.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await out_file.write(chunk)
        read_elapsed = time.perf_counter() - read_started_at

        transcribe_started_at = time.perf_counter()
        result = await asyncio.wait_for(
            asyncio.to_thread(voice.transcribe_file, audio_path, language),
            timeout=app_settings.STT_TIMEOUT_SECONDS,
        )
        transcribe_elapsed = time.perf_counter() - transcribe_started_at
        logger.info(
            "STT completed file=%s read_s=%.2f transcribe_s=%.2f language=%s duration_ms=%s",
            audio.filename,
            read_elapsed,
            transcribe_elapsed,
            result.language,
            result.duration_ms,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "signal": ResponseStatus.STT_SUCCESS.value,
                "text": result.text,
                "language": result.language,
                "duration_ms": result.duration_ms,
            },
        )
    except asyncio.TimeoutError:
        logger.warning(
            "STT timed out after %ss for file=%s path=%s",
            app_settings.STT_TIMEOUT_SECONDS,
            audio.filename,
            audio_path,
        )
        return JSONResponse(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            content={
                "signal": ResponseStatus.STT_TIMEOUT.value,
                "message": f"Speech-to-text exceeded {app_settings.STT_TIMEOUT_SECONDS} seconds",
            },
        )
    except Exception as e:
        logger.exception("STT failed for file=%s", audio.filename)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseStatus.STT_FAILED.value, "message": str(e)},
        )
    finally:
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass


@voice_router.post("/tts")
async def tts_endpoint(
    request: Request,
    tts_request: TTSRequest,
):
    if (tts_request.format or "wav").lower() != "wav":
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseStatus.TTS_FAILED.value, "message": "Only format=wav is supported"},
        )

    voice = request.app.state.voice_controller
    try:
        wav_bytes = await asyncio.to_thread(voice.synthesize_to_wav_bytes, tts_request.text)
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseStatus.TTS_FAILED.value, "message": str(e)},
        )


@voice_router.post("/chat/{project_id}")
async def voice_chat_endpoint(
    request: Request,
    project_id: int,
    audio: UploadFile = File(...),
    limit: int = Form(30),
    return_audio_base64: bool = Form(True),
    language: Optional[str] = None,
    app_settings: Settings = Depends(get_settings),
):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=project_id)
    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseStatus.PROJECT_NOT_FOUND.value},
        )

    voice = request.app.state.voice_controller
    ext = os.path.splitext(audio.filename or "audio")[1] or ".bin"
    audio_path = voice.unique_audio_path(project_id=str(project_id), suffix=ext)

    try:
        async with aiofiles.open(audio_path, "wb") as out_file:
            while chunk := await audio.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await out_file.write(chunk)

        stt = await asyncio.wait_for(
            asyncio.to_thread(voice.transcribe_file, audio_path, language),
            timeout=app_settings.STT_TIMEOUT_SECONDS,
        )
        if not stt.text:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"signal": ResponseStatus.STT_FAILED.value, "message": "No speech detected"},
            )

        nlp_controller = NLPController(
            embedding_client=request.app.embedding_client,
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            template_parser=request.app.template_parser,
        )
        rag_answer, full_prompt, chat_history = await nlp_controller.answer_rag_question(
            query=stt.text,
            project=project,
            limit=limit,
        )

        if not rag_answer:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseStatus.RAG_ANSWER_FAILED.value,
                    "message": "No answer could be generated from the retrieved documents",
                    "transcript": stt.text,
                },
            )

        wav_bytes = await asyncio.to_thread(voice.synthesize_to_wav_bytes, str(rag_answer))
        if return_audio_base64:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "signal": ResponseStatus.VOICE_CHAT_SUCCESS.value,
                    "transcript": stt.text,
                    "answer": rag_answer,
                    "audio_base64": voice.wav_bytes_to_base64(wav_bytes),
                    "audio_mime_type": "audio/wav",
                    "full_prompt": full_prompt,
                    "chat_history": chat_history,
                },
            )

        return Response(content=wav_bytes, media_type="audio/wav", headers={"X-Transcript": stt.text})
    except asyncio.TimeoutError:
        logger.warning(
            "Voice chat STT timed out after %ss for project_id=%s file=%s",
            app_settings.STT_TIMEOUT_SECONDS,
            project_id,
            audio.filename,
        )
        return JSONResponse(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            content={
                "signal": ResponseStatus.VOICE_CHAT_TIMEOUT.value,
                "message": f"Speech-to-text exceeded {app_settings.STT_TIMEOUT_SECONDS} seconds",
            },
        )
    except Exception as e:
        logger.exception("Voice chat failed for project_id=%s file=%s", project_id, audio.filename)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseStatus.VOICE_CHAT_FAILED.value, "message": str(e)},
        )
    finally:
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass
