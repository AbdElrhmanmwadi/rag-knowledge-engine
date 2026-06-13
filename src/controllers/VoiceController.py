import asyncio
import base64
import logging
import uuid
from pathlib import Path
from typing import Optional

from controllers.NLPController import NLPController
from helpers.streaming import split_sentences
from services.agent_service import detect_lang
from stores.llm.voice import STTResult, VoiceProviderInterface

logger = logging.getLogger("uvicorn.error")


class VoiceController:
    def __init__(self, settings, voice_provider: VoiceProviderInterface):
        self.settings = settings
        self.voice_provider = voice_provider

    def warm_up_stt(self) -> None:
        self.voice_provider.warm_up_stt()

    def transcribe_file(self, audio_path: str, language: Optional[str] = None) -> STTResult:
        return self.voice_provider.transcribe_file(audio_path=audio_path, language=language)

    def synthesize_to_wav_bytes(self, text: str, language: Optional[str] = None) -> bytes:
        return self.voice_provider.synthesize_to_wav_bytes(text=text, language=language)

    def wav_bytes_to_base64(self, wav_bytes: bytes) -> str:
        return base64.b64encode(wav_bytes).decode("ascii")

    async def voice_chat_stream(self, audio_path, project, nlp_controller: NLPController, limit, language=None):
        """Yield {"event","data"} dicts for the SSE voice-chat path.

        Order: transcript (after STT) -> delta* (answer text) -> audio* (one wav per
        spoken sentence) -> done. On failure yields error and stops. Persists nothing
        (this endpoint never did), so a client disconnect just stops cleanly.
        """
        # 1. STT must complete before anything else — can't answer half a question.
        stt = await asyncio.wait_for(
            asyncio.to_thread(self.transcribe_file, audio_path, language),
            timeout=self.settings.STT_TIMEOUT_SECONDS,
        )
        if not stt.text:
            yield {"event": "error", "data": {"detail": "No speech detected"}}
            return
        yield {"event": "transcript", "data": {"text": stt.text}}

        # 2. Stream the answer text; synthesize audio one sentence at a time.
        answer_parts = []
        buffer = ""
        seq = 0
        async for chunk in nlp_controller.answer_rag_question_stream(
            query=stt.text, project=project, limit=limit
        ):
            if not chunk:
                continue
            answer_parts.append(chunk)
            yield {"event": "delta", "data": {"text": chunk}}
            buffer += chunk
            sentences, buffer = split_sentences(buffer)
            for sentence in sentences:
                seq += 1
                async for event in self._speak(sentence, seq):
                    yield event

        # 3. Flush the trailing partial sentence (no terminator) as final audio.
        tail = buffer.strip()
        if tail:
            seq += 1
            async for event in self._speak(tail, seq):
                yield event

        answer = "".join(answer_parts).strip()
        if not answer:
            # Mirror the non-stream "no answer" outcome.
            yield {
                "event": "done",
                "data": {
                    "answer": "",
                    "signal": "rag_answer_failed",
                    "message": "No answer could be generated from the retrieved documents",
                },
            }
            return
        yield {"event": "done", "data": {"answer": answer, "signal": "voice_chat_success"}}

    async def _speak(self, sentence: str, seq: int):
        """Synthesize one sentence to a wav and yield it as an audio event.

        TTS voice follows the sentence's own language so a mixed-language answer is
        spoken correctly per sentence. A synthesis failure for one sentence is logged
        and skipped (text already streamed) rather than killing the whole stream.
        """
        try:
            wav_bytes = await asyncio.to_thread(
                self.synthesize_to_wav_bytes, sentence, detect_lang(sentence)
            )
        except Exception:
            logger.exception("TTS failed for one sentence (seq=%s); skipping its audio", seq)
            return
        yield {
            "event": "audio",
            "data": {
                "audio_base64": self.wav_bytes_to_base64(wav_bytes),
                "mime_type": "audio/wav",
                "seq": seq,
            },
        }

    def unique_audio_path(self, project_id: str, suffix: str) -> str:
        if self.settings.STORAGE_ROOT:
            base_dir = Path(self.settings.STORAGE_ROOT) / "voice" / str(project_id)
        else:
            base_dir = Path(__file__).resolve().parent.parent / "assets" / "voice" / str(project_id)
        base_dir.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}{suffix}"
        return str(base_dir / name)
