import asyncio
import logging
import os
import time
from typing import Optional
from urllib.parse import quote

import aiofiles
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response, StreamingResponse

from controllers.NLPController import NLPController
from helpers.auth_dependencies import get_current_user
from helpers.config import Settings, get_settings
from helpers.db import get_db
from helpers.streaming import sse
from models.enums.ResponseEnums import ResponseStatus
from models.user_model import User
from services.agent_service import detect_lang
from services.project_access import get_project_for_user
from sqlalchemy.ext.asyncio import AsyncSession
from routes.schemes.voice import TTSRequest


voice_router = APIRouter(
    prefix="/api/v1/voice",
    tags=["api-v1", "voice"],
)
logger = logging.getLogger("uvicorn.error")

# Formats ffmpeg can decode for Whisper; anything else is rejected up front so
# arbitrary files never reach disk or a subprocess.
_ALLOWED_AUDIO_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".oga", ".webm",
    ".flac", ".aac", ".opus", ".wma", ".amr", ".3gp",
}


def _validate_audio_extension(filename: Optional[str]) -> Optional[str]:
    """Return the lowercased extension, or None when the type is not allowed."""
    ext = os.path.splitext(filename or "")[1].lower()
    return ext if ext in _ALLOWED_AUDIO_EXTENSIONS else None


async def _write_upload_capped(audio: UploadFile, audio_path: str, app_settings: Settings) -> bool:
    """Stream the upload to disk. Returns False when it exceeds FILE_MAX_SIZE (MB)."""
    max_bytes = app_settings.FILE_MAX_SIZE * 1024 * 1024
    written = 0
    async with aiofiles.open(audio_path, "wb") as out_file:
        while chunk := await audio.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
            written += len(chunk)
            if written > max_bytes:
                return False
            await out_file.write(chunk)
    return True


def _file_type_error() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "signal": ResponseStatus.FILE_TYPE_NOT_SUPPORTED.value,
            "message": "Unsupported audio type. Allowed: " + ", ".join(sorted(_ALLOWED_AUDIO_EXTENSIONS)),
        },
    )


def _file_size_error(app_settings: Settings) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={
            "signal": ResponseStatus.FILE_SIZE_EXCEEDED.value,
            "message": f"Audio file exceeds the {app_settings.FILE_MAX_SIZE} MB limit",
        },
    )


@voice_router.post("/stt")
async def stt_endpoint(
    request: Request,
    audio: UploadFile = File(...),
    language: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    app_settings: Settings = Depends(get_settings),
):
    ext = _validate_audio_extension(audio.filename)
    if ext is None:
        return _file_type_error()

    voice = request.app.state.voice_controller
    audio_path = voice.unique_audio_path(project_id="tmp", suffix=ext)
    try:
        read_started_at = time.perf_counter()
        if not await _write_upload_capped(audio, audio_path, app_settings):
            return _file_size_error(app_settings)
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
    except Exception:
        # Details (paths, ffmpeg output) stay in the log; the client gets a generic message.
        logger.exception("STT failed for file=%s", audio.filename)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseStatus.STT_FAILED.value, "message": "Speech-to-text failed"},
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
    current_user: User = Depends(get_current_user),
):
    if (tts_request.format or "wav").lower() != "wav":
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseStatus.TTS_FAILED.value, "message": "Only format=wav is supported"},
        )

    voice = request.app.state.voice_controller
    try:
        wav_bytes = await asyncio.to_thread(
            voice.synthesize_to_wav_bytes, tts_request.text, detect_lang(tts_request.text)
        )
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception:
        logger.exception("TTS failed for text length=%d", len(tts_request.text))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseStatus.TTS_FAILED.value, "message": "Text-to-speech failed"},
        )


@voice_router.post("/chat/{project_id}")
async def voice_chat_endpoint(
    request: Request,
    project_id: int,
    audio: UploadFile = File(...),
    limit: int = Form(30),
    return_audio_base64: bool = Form(True),
    stream: bool = Form(False),
    language: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    app_settings: Settings = Depends(get_settings),
):
    # create_if_missing=False: chatting must not silently create projects —
    # same behavior as the text agent endpoint (404 for an unknown project).
    project = await get_project_for_user(
        db, project_id=project_id, user_id=current_user.id, create_if_missing=False
    )

    ext = _validate_audio_extension(audio.filename)
    if ext is None:
        return _file_type_error()

    voice = request.app.state.voice_controller
    audio_path = voice.unique_audio_path(project_id=str(project_id), suffix=ext)
    # The streaming branch hands the temp file to a generator that outlives this
    # function, so it owns cleanup; the finally below must not delete it early.
    stream_owns_cleanup = False

    try:
        if not await _write_upload_capped(audio, audio_path, app_settings):
            return _file_size_error(app_settings)

        if stream:
            nlp_controller = NLPController(
                embedding_client=request.app.embedding_client,
                vectordb_client=request.app.vectordb_client,
                generation_client=request.app.generation_client,
                template_parser=request.app.template_parser,
            )

            async def event_stream():
                try:
                    async for event in voice.voice_chat_stream(
                        audio_path=audio_path,
                        project=project,
                        nlp_controller=nlp_controller,
                        limit=limit,
                        language=language,
                    ):
                        yield sse(event["event"], event["data"])
                except asyncio.TimeoutError:
                    logger.warning("Voice chat STT timed out (stream) for project_id=%s", project_id)
                    yield sse("error", {"detail": f"Speech-to-text exceeded {app_settings.STT_TIMEOUT_SECONDS} seconds"})
                except Exception:
                    logger.exception("Voice chat stream failed for project_id=%s", project_id)
                    yield sse("error", {"detail": "Voice chat failed"})
                finally:
                    try:
                        if os.path.exists(audio_path):
                            os.remove(audio_path)
                    except Exception:
                        pass

            stream_owns_cleanup = True
            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

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
        # full_prompt/chat_history are intentionally discarded: they contain the
        # system prompt and raw retrieved chunks and must never reach the client.
        rag_answer, _full_prompt, _chat_history = await nlp_controller.answer_rag_question(
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

        # Voice follows the answer's language, not the question's: a question
        # asked in English can still get an Arabic answer (and vice versa).
        wav_bytes = await asyncio.to_thread(
            voice.synthesize_to_wav_bytes, str(rag_answer), detect_lang(str(rag_answer))
        )
        if return_audio_base64:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "signal": ResponseStatus.VOICE_CHAT_SUCCESS.value,
                    "transcript": stt.text,
                    "answer": rag_answer,
                    "audio_base64": voice.wav_bytes_to_base64(wav_bytes),
                    "audio_mime_type": "audio/wav",
                },
            )

        # HTTP headers are latin-1; percent-encode so Arabic transcripts survive
        # (client decodes with decodeURIComponent).
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={"X-Transcript": quote(stt.text, safe="")},
        )
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
    except Exception:
        # Details (paths, ffmpeg/piper output) stay in the log; the client gets a generic message.
        logger.exception("Voice chat failed for project_id=%s file=%s", project_id, audio.filename)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseStatus.VOICE_CHAT_FAILED.value, "message": "Voice chat failed"},
        )
    finally:
        # In the streaming branch the generator owns the temp file; deleting it here
        # would pull it out from under the not-yet-consumed stream.
        if not stream_owns_cleanup:
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception:
                pass
