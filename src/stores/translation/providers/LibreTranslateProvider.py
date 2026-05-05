import asyncio
import json
import socket
import time
import uuid
from http.client import RemoteDisconnected
from typing import Optional
from urllib import error, request

from stores.translation.TranslationProviderInterface import TranslationProviderInterface
from stores.translation.TranslationExceptions import TranslationException


class LibreTranslateProvider(TranslationProviderInterface):
    def __init__(
        self,
        api_key: str = None,
        default_target_lang: str = "ar",
        base_url: str = "http://localhost:5000/translate",
        file_endpoint_url: str = "http://localhost:5000/translate/file",
        timeout_seconds: int = 60,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.0
    ):
        self.api_key = api_key
        self.default_target_lang = default_target_lang
        self.base_url = base_url
        self.file_endpoint_url = file_endpoint_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, int(max_retries or 0))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds or 0.0))
        self.invalid_language_values = {"string", "null", "none", "undefined"}
        self.language_aliases = {
            "arabic": "ar",
            "ar": "ar",
            "english": "en",
            "en": "en",
            "french": "fr",
            "fr": "fr",
            "german": "de",
            "de": "de",
            "spanish": "es",
            "es": "es"
        }

    def normalize_language(self, language: str, fallback: str = None):
        """
        Normalize language code using alias mapping.
        
        Args:
            language: Language code or name (e.g., 'en', 'english', 'ar', 'arabic')
            fallback: Fallback value if language is None or invalid
            
        Returns:
            Normalized language code
            
        Raises:
            TranslationException: If language is invalid (like 'string', 'null', 'none', 'undefined')
        """
        if not language:
            return fallback
        normalized = str(language).strip().lower()
        if normalized in self.invalid_language_values:
            raise TranslationException(
                f"Invalid language value '{language}'. Please provide a language code like 'en' or 'ar'.",
                api_error_code="validation"
            )
        return self.language_aliases.get(normalized, normalized)

    async def translate_text(
        self,
        text: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None
    ) -> str:
        """
        Translate text asynchronously.
        
        Args:
            text: The text to translate
            source_lang: Source language code. If None, auto-detects (sends "auto" to API)
            target_lang: Target language code (required). Will be normalized (ar/arabic → ar, etc.)
            
        Returns:
            Translated text
            
        Raises:
            TranslationException: If translation fails
        """
        if text is None:
            return ""
        
        if target_lang is None:
            raise TranslationException(
                "Target language is required for translation",
                api_error_code="validation"
            )
        
        # Prepare payload with auto-detect logic
        payload = self._build_text_request_payload(text, source_lang, target_lang)
        
        # Build HTTP request
        http_request = request.Request(
            url=self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        # Execute asynchronously using asyncio.to_thread for urllib (which is sync-only)
        response_payload = await asyncio.to_thread(
            self._send_request_with_retries,
            http_request
        )
        
        # Parse and return response
        return self._parse_text_response(response_payload)

    def _build_text_request_payload(
        self,
        text: str,
        source_lang: Optional[str],
        target_lang: Optional[str]
    ) -> dict:
        """Build request payload for text translation."""
        source = self.normalize_language(source_lang, "auto") if source_lang else "auto"
        target = self.normalize_language(target_lang, None)
        
        payload = {
            "q": text,
            "source": source,
            "target": target,
            "format": "text"
        }
        if self.api_key:
            payload["api_key"] = self.api_key
        return payload

    def _parse_text_response(self, response_payload: dict) -> str:
        """
        Parse and validate text translation response.
        
        Raises:
            TranslationException: If response doesn't contain translatedText
        """
        translated_text = response_payload.get("translatedText")
        if translated_text is None:
            raise TranslationException(
                "LibreTranslate response did not include translatedText",
                api_error_code="invalid_response",
                details=response_payload
            )
        return translated_text

    async def translate_file(
        self,
        file_bytes: bytes,
        filename: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None
    ) -> bytes:
        """
        Translate a file asynchronously using LibreTranslate's /translate/file endpoint.
        
        Args:
            file_bytes: The file content as bytes
            filename: The original filename (used for multipart form data)
            source_lang: Source language code. If None, auto-detects (sends "auto" to API)
            target_lang: Target language code (required). Will be normalized.
            
        Returns:
            The translated file content as bytes
            
        Raises:
            TranslationException: If translation service returns an error
        """
        if target_lang is None:
            raise TranslationException(
                "Target language is required for translation",
                api_error_code="validation"
            )
        
        source_language = self.normalize_language(source_lang, "auto") if source_lang else "auto"
        target_language = self.normalize_language(target_lang, None)
        
        # Construct multipart form data
        boundary = str(uuid.uuid4())
        body = self._build_multipart_form_data(
            boundary=boundary,
            file_bytes=file_bytes,
            filename=filename,
            source_lang=source_language,
            target_lang=target_language
        )
        
        # Build request to file endpoint
        http_request = request.Request(
            url=self.file_endpoint_url,
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}"
            },
            method="POST"
        )
        
        if self.api_key:
            http_request.add_header("Authorization", f"Bearer {self.api_key}")
        
        # Execute the request asynchronously
        translated_file_bytes = await asyncio.to_thread(
            self._send_file_request_with_retries,
            http_request
        )
        
        return translated_file_bytes

    def _build_multipart_form_data(
        self,
        boundary: str,
        file_bytes: bytes,
        filename: str,
        source_lang: str,
        target_lang: str
    ) -> bytes:
        """Build multipart/form-data body for file upload."""
        lines = []
        
        # Add source language field
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(b'Content-Disposition: form-data; name="source"')
        lines.append(b"")
        lines.append(source_lang.encode("utf-8"))
        
        # Add target language field
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(b'Content-Disposition: form-data; name="target"')
        lines.append(b"")
        lines.append(target_lang.encode("utf-8"))
        
        # Add file field
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode("utf-8"))
        lines.append(b"Content-Type: application/octet-stream")
        lines.append(b"")
        lines.append(file_bytes)
        
        # Add closing boundary
        lines.append(f"--{boundary}--".encode("utf-8"))
        lines.append(b"")
        
        return b"\r\n".join(lines)

    def _send_file_request_with_retries(self, http_request: request.Request) -> bytes:
        """Send file translation request with retries, returning binary response."""
        attempts = self.max_retries + 1
        last_error = None

        for attempt in range(1, attempts + 1):
            try:
                with request.urlopen(http_request, timeout=120.0) as response:
                    return response.read()
            except error.HTTPError as exc:
                error_payload = exc.read().decode("utf-8", errors="replace")
                raise TranslationException(
                    f"LibreTranslate HTTP {exc.code}: {error_payload}",
                    api_error_code=str(exc.code),
                    details={"status_code": exc.code, "response": error_payload}
                ) from exc
            except error.URLError as exc:
                last_error = exc.reason
                if self._should_retry(exc.reason, attempt, attempts):
                    self._sleep_before_retry(attempt)
                    continue
                raise TranslationException(
                    self._build_connection_error_message(exc.reason, attempt, attempts),
                    api_error_code="connection",
                    details={"reason": str(exc.reason)}
                ) from exc
            except (ConnectionResetError, RemoteDisconnected, TimeoutError, socket.timeout, OSError) as exc:
                last_error = exc
                if self._should_retry(exc, attempt, attempts):
                    self._sleep_before_retry(attempt)
                    continue
                raise TranslationException(
                    self._build_connection_error_message(exc, attempt, attempts),
                    api_error_code="connection",
                    details={"error_type": type(exc).__name__, "error": str(exc)}
                ) from exc

        raise TranslationException(
            self._build_connection_error_message(last_error, attempts, attempts),
            api_error_code="connection",
            details={"error": str(last_error)}
        )

    def _send_request_with_retries(self, http_request: request.Request):
        """Send text translation request with retries, returning parsed JSON response."""
        attempts = self.max_retries + 1
        last_error = None

        for attempt in range(1, attempts + 1):
            try:
                with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except error.HTTPError as exc:
                error_payload = exc.read().decode("utf-8", errors="replace")
                raise TranslationException(
                    f"LibreTranslate HTTP {exc.code}: {error_payload}",
                    api_error_code=str(exc.code),
                    details={"status_code": exc.code, "response": error_payload}
                ) from exc
            except error.URLError as exc:
                last_error = exc.reason
                if self._should_retry(exc.reason, attempt, attempts):
                    self._sleep_before_retry(attempt)
                    continue
                raise TranslationException(
                    self._build_connection_error_message(exc.reason, attempt, attempts),
                    api_error_code="connection",
                    details={"reason": str(exc.reason)}
                ) from exc
            except (ConnectionResetError, RemoteDisconnected, TimeoutError, socket.timeout, OSError) as exc:
                last_error = exc
                if self._should_retry(exc, attempt, attempts):
                    self._sleep_before_retry(attempt)
                    continue
                raise TranslationException(
                    self._build_connection_error_message(exc, attempt, attempts),
                    api_error_code="connection",
                    details={"error_type": type(exc).__name__, "error": str(exc)}
                ) from exc
            except json.JSONDecodeError as exc:
                raise TranslationException(
                    "LibreTranslate returned an invalid JSON response",
                    api_error_code="invalid_response",
                    details={"error": str(exc)}
                ) from exc

        raise TranslationException(
            self._build_connection_error_message(last_error, attempts, attempts),
            api_error_code="connection",
            details={"error": str(last_error)}
        )


    def _should_retry(self, exc: Exception, attempt: int, attempts: int):
        return attempt < attempts and self._is_transient_connection_error(exc)

    def _is_transient_connection_error(self, exc: Exception):
        transient_errors = (
            ConnectionResetError,
            RemoteDisconnected,
            TimeoutError,
            socket.timeout
        )
        if isinstance(exc, transient_errors):
            return True

        if isinstance(exc, OSError):
            return exc.errno in {54, 104, 110, 111, 10053, 10054, 10060, 10061}

        message = str(exc).lower()
        return any(
            token in message
            for token in (
                "connection reset",
                "connection aborted",
                "connection was aborted",
                "connection refused",
                "timed out",
                "remote end closed connection",
                "temporarily unavailable"
            )
        )

    def _sleep_before_retry(self, attempt: int):
        if self.retry_backoff_seconds > 0:
            time.sleep(self.retry_backoff_seconds * attempt)

    def _build_connection_error_message(self, exc: Exception, attempt: int, attempts: int):
        base_message = str(exc) if exc else "Unknown connection error"
        if attempt >= attempts:
            return (
                f"LibreTranslate request failed after {attempts} attempt(s): {base_message}. "
                f"Verify that the translation service is running and reachable at {self.base_url}."
            )

        return f"LibreTranslate request failed on attempt {attempt}/{attempts}: {base_message}"
