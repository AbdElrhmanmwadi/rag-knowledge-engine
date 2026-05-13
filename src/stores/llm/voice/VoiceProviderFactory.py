from stores.llm.voice.providers import LocalVoiceProvider


class VoiceProviderFactory:
    def __init__(self, config):
        self.config = config

    def create(self, stt_provider: str, tts_provider: str):
        normalized_stt_provider = (stt_provider or "").strip().upper()
        normalized_tts_provider = (tts_provider or "").strip().upper()

        if normalized_stt_provider == "FASTER_WHISPER" and normalized_tts_provider == "PIPER":
            return LocalVoiceProvider(settings=self.config)

        raise ValueError(
            f"Unsupported voice providers combination: STT={normalized_stt_provider}, "
            f"TTS={normalized_tts_provider}"
        )
