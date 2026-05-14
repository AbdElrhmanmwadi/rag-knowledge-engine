import base64
import uuid
from pathlib import Path
from typing import Optional

from stores.llm.voice import STTResult, VoiceProviderInterface


class VoiceController:
    def __init__(self, settings, voice_provider: VoiceProviderInterface):
        self.settings = settings
        self.voice_provider = voice_provider

    def warm_up_stt(self) -> None:
        self.voice_provider.warm_up_stt()

    def transcribe_file(self, audio_path: str, language: Optional[str] = None) -> STTResult:
        return self.voice_provider.transcribe_file(audio_path=audio_path, language=language)

    def synthesize_to_wav_bytes(self, text: str) -> bytes:
        return self.voice_provider.synthesize_to_wav_bytes(text=text)

    def wav_bytes_to_base64(self, wav_bytes: bytes) -> str:
        return base64.b64encode(wav_bytes).decode("ascii")

    def unique_audio_path(self, project_id: str, suffix: str) -> str:
        if self.settings.STORAGE_ROOT:
            base_dir = Path(self.settings.STORAGE_ROOT) / "voice" / str(project_id)
        else:
            base_dir = Path(__file__).resolve().parent.parent / "assets" / "voice" / str(project_id)
        base_dir.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}{suffix}"
        return str(base_dir / name)
