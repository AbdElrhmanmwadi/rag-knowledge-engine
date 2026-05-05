from abc import ABC, abstractmethod
from typing import Optional


class TranslationProviderInterface(ABC):
    """
    Abstract base class for translation providers.
    
    Defines the contract that all translation provider implementations must follow.
    Supports auto-detection of source language (source_lang=None) with explicit target language.
    """

    @abstractmethod
    async def translate_text(
        self,
        text: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None
    ) -> str:
        """
        Translate text from source language to target language.

        Args:
            text: The text to translate.
            source_lang: Source language code (e.g., 'en', 'ar'). 
                        If None, uses "auto" for auto-detection.
            target_lang: Target language code (e.g., 'en', 'ar'). 
                        Required; cannot be None.

        Returns:
            Translated text as a string.

        Raises:
            TranslationException: If translation fails for any reason
                                 (API error, connection issue, timeout, validation error, etc.).
        """
        pass

    @abstractmethod
    async def translate_file(
        self,
        file_bytes: bytes,
        filename: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None
    ) -> bytes:
        """
        Translate a file from source language to target language.

        Args:
            file_bytes: The file content as bytes.
            filename: The original filename (used for content-type detection).
            source_lang: Source language code (e.g., 'en', 'ar'). 
                        If None, uses "auto" for auto-detection.
            target_lang: Target language code (e.g., 'en', 'ar'). 
                        Required; cannot be None.

        Returns:
            Translated file content as bytes.

        Raises:
            TranslationException: If translation fails for any reason
                                 (API error, connection issue, timeout, validation error, etc.).
        """
        pass
