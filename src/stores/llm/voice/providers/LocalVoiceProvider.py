import logging
import os
import subprocess
import tempfile
import wave
from pathlib import Path
from threading import Lock
from typing import Optional

from stores.llm.voice.VoiceProviderInterface import STTResult, VoiceProviderInterface


logger = logging.getLogger("uvicorn.error")


class LocalVoiceProvider(VoiceProviderInterface):
    def __init__(self, settings):
        self.settings = settings
        self._whisper_model = None
        self._whisper_model_lock = Lock()

    def warm_up_stt(self) -> None:
        self._ensure_whisper_model()

    def _ensure_whisper_model(self):
        if self._whisper_model is not None:
            return self._whisper_model

        with self._whisper_model_lock:
            if self._whisper_model is not None:
                return self._whisper_model

            try:
                from faster_whisper import WhisperModel
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "faster-whisper is not installed in the running environment"
                ) from exc

            model_size = self.settings.STT_MODEL_SIZE or "small"
            device = self.settings.STT_DEVICE or "cpu"
            compute_type = self.settings.STT_COMPUTE_TYPE or "int8"
            logger.info(
                "Loading Whisper model size=%s device=%s compute_type=%s",
                model_size,
                device,
                compute_type,
            )
            self._whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("Whisper model loaded successfully")
            return self._whisper_model

    def _ffmpeg_path(self) -> str:
        return self.settings.FFMPEG_PATH or "ffmpeg"

    def _convert_to_wav16k_mono(self, input_path: str, output_path: str) -> None:
        cmd = [
            self._ffmpeg_path(),
            "-y",
            "-i",
            input_path,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            output_path,
        ]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.settings.FFMPEG_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("ffmpeg conversion timed out") from exc
        except FileNotFoundError as exc:
            raise RuntimeError(
                "ffmpeg executable was not found. Set FFMPEG_PATH or upload a wav file"
            ) from exc
        if completed.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {completed.stderr.strip() or completed.stdout.strip()}")

    def _wav_duration_ms(self, wav_path: str) -> Optional[int]:
        try:
            with wave.open(wav_path, "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                if not rate:
                    return None
                return int((frames / rate) * 1000)
        except Exception:
            return None

    def transcribe_file(self, audio_path: str, language: Optional[str] = None) -> STTResult:
        model = self._ensure_whisper_model()

        input_ext = Path(audio_path).suffix.lower()
        wav_path = audio_path
        tmp_wav = None
        if input_ext != ".wav":
            tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            tmp_wav.close()
            self._convert_to_wav16k_mono(audio_path, tmp_wav.name)
            wav_path = tmp_wav.name

        try:
            segments, info = model.transcribe(
                wav_path,
                language=language,
                vad_filter=True,
            )
            text = "".join(segment.text for segment in segments).strip()
            duration_ms = self._wav_duration_ms(wav_path)
            return STTResult(
                text=text,
                language=info.language,
                duration_ms=duration_ms,
            )
        finally:
            if tmp_wav is not None:
                try:
                    os.remove(tmp_wav.name)
                except Exception:
                    pass

    def _piper_exe(self) -> str:
        exe = self.settings.PIPER_EXE_PATH
        if not exe:
            raise RuntimeError("PIPER_EXE_PATH is not configured")
        return exe

    def _piper_model(self) -> str:
        model_path = self.settings.PIPER_MODEL_PATH
        if not model_path:
            raise RuntimeError("PIPER_MODEL_PATH is not configured")
        return model_path

    def synthesize_to_wav_bytes(self, text: str) -> bytes:
        exe = self._piper_exe()
        model = self._piper_model()

        out_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        out_file.close()
        try:
            cmd = [exe, "-m", model, "-f", out_file.name]
            completed = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True)
            if completed.returncode != 0:
                stderr = (completed.stderr or b"").decode("utf-8", errors="ignore").strip()
                stdout = (completed.stdout or b"").decode("utf-8", errors="ignore").strip()
                raise RuntimeError(f"piper failed: {stderr or stdout}")
            with open(out_file.name, "rb") as file_handle:
                return file_handle.read()
        finally:
            try:
                os.remove(out_file.name)
            except Exception:
                pass
