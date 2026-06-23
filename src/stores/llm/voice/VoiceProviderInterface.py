from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class STTResult:
    text: str
    language: Optional[str] = None
    duration_ms: Optional[int] = None


class VoiceProviderInterface(ABC):
    @abstractmethod
    def warm_up_stt(self) -> None:
        pass

    @abstractmethod
    def transcribe_file(self, audio_path: str, language: Optional[str] = None) -> STTResult:
        pass

    @abstractmethod
    def synthesize_to_wav_bytes(self, text: str, language: Optional[str] = None) -> bytes:
        """language selects the voice model (e.g. "ar"); None uses the default voice."""
        pass
