from .providers.LibreTranslateProvider import LibreTranslateProvider


class TranslationProviderFactory:
    def __init__(self, config):
        self.config = config

    def create(self, provider: str):
        if provider == "LIBRETRANSLATE":
            return LibreTranslateProvider(
                api_key=self.config.TRANSLATION_API_KEY,
                default_target_lang=self.config.DEFAULT_TARGET_LANG,
                base_url=self.config.TRANSLATION_BASE_URL,
                file_endpoint_url=self.config.TRANSLATION_FILE_ENDPOINT_URL,
                timeout_seconds=self.config.TRANSLATION_TIMEOUT_SECONDS,
                max_retries=self.config.TRANSLATION_MAX_RETRIES,
                retry_backoff_seconds=self.config.TRANSLATION_RETRY_BACKOFF_SECONDS
            )
        raise ValueError(f"Unsupported translation provider: {provider}")
