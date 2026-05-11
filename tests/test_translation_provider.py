import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from urllib import error


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from routes.schemes.translation import TranslationFileRequest
from stores.translation.providers.LibreTranslateProvider import LibreTranslateProvider
from stores.translation.TranslationExceptions import TranslationException


class FakeResponse:
    def __init__(self, payload, content_type="application/json"):
        self.payload = payload
        self.headers = {"Content-Type": content_type}

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TranslationProviderTests(unittest.TestCase):
    """Test suite for LibreTranslateProvider with async support."""
    
    def _async_test(self, coro):
        """Helper to run async test methods."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)
    
    def test_translate_text_retries_on_connection_reset(self):
        """Test that translate_text retries on transient connection errors."""
        provider = LibreTranslateProvider(
            base_url="http://localhost:5000/translate",
            max_retries=2,
            retry_backoff_seconds=0
        )
        responses = [
            ConnectionResetError(104, "Connection reset by peer"),
            FakeResponse({"translatedText": "translated"})
        ]

        def fake_urlopen(*args, **kwargs):
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        async def run_test():
            with patch("stores.translation.providers.LibreTranslateProvider.request.urlopen", side_effect=fake_urlopen):
                translated = await provider.translate_text("hello", source_lang="en", target_lang="ar")
            return translated

        translated = self._async_test(run_test())
        self.assertEqual(translated, "translated")

    def test_translate_text_raises_translation_exception_after_retries(self):
        """Test that translate_text raises TranslationException after max retries."""
        provider = LibreTranslateProvider(
            base_url="http://localhost:5000/translate",
            max_retries=1,
            retry_backoff_seconds=0
        )

        async def run_test():
            with patch(
                "stores.translation.providers.LibreTranslateProvider.request.urlopen",
                side_effect=ConnectionResetError(104, "Connection reset by peer")
            ):
                with self.assertRaises(TranslationException) as exc_info:
                    await provider.translate_text("hello", source_lang="en", target_lang="ar")
            return exc_info.exception

        exc = self._async_test(run_test())
        self.assertIn("failed after 2 attempt(s)", exc.message)
        self.assertIn("http://localhost:5000/translate", exc.message)
        self.assertEqual(exc.api_error_code, "connection")

    def test_translate_text_rejects_invalid_target_language(self):
        """Test that translate_text raises TranslationException for invalid language codes."""
        provider = LibreTranslateProvider()

        async def run_test():
            with self.assertRaises(TranslationException) as exc_info:
                await provider.translate_text("hello", source_lang="en", target_lang="string")
            return exc_info.exception

        exc = self._async_test(run_test())
        self.assertIn("Invalid language value", exc.message)
        self.assertEqual(exc.api_error_code, "validation")

    def test_translate_text_requires_target_language(self):
        """Test that translate_text requires target language (cannot be None)."""
        provider = LibreTranslateProvider()

        async def run_test():
            with self.assertRaises(TranslationException) as exc_info:
                await provider.translate_text("hello", source_lang="en", target_lang=None)
            return exc_info.exception

        exc = self._async_test(run_test())
        self.assertIn("Target language is required", exc.message)
        self.assertEqual(exc.api_error_code, "validation")

    def test_translate_text_auto_detects_source_language(self):
        """Test that translate_text auto-detects source language when source_lang=None."""
        provider = LibreTranslateProvider(
            base_url="http://localhost:5000/translate"
        )

        def fake_urlopen(*args, **kwargs):
            # Verify that the request payload has source="auto"
            request_obj = args[0]
            payload = json.loads(request_obj.data.decode("utf-8"))
            self.assertEqual(payload["source"], "auto")
            return FakeResponse({"translatedText": "مرحبا"})

        async def run_test():
            with patch("stores.translation.providers.LibreTranslateProvider.request.urlopen", side_effect=fake_urlopen):
                translated = await provider.translate_text("hello", source_lang=None, target_lang="ar")
            return translated

        translated = self._async_test(run_test())
        self.assertEqual(translated, "مرحبا")

    def test_translate_text_surfaces_http_errors(self):
        """Test that translate_text raises TranslationException for HTTP errors."""
        provider = LibreTranslateProvider()
        http_error = error.HTTPError(
            url="http://localhost:5000/translate",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=None
        )
        http_error.read = lambda: b'{"error":"unsupported target"}'

        async def run_test():
            with patch(
                "stores.translation.providers.LibreTranslateProvider.request.urlopen",
                side_effect=http_error
            ):
                with self.assertRaises(TranslationException) as exc_info:
                    await provider.translate_text("hello", source_lang="en", target_lang="zz")
            return exc_info.exception

        exc = self._async_test(run_test())
        self.assertIn("LibreTranslate HTTP 400", exc.message)
        self.assertEqual(exc.api_error_code, "400")

    def test_translate_file_requires_target_language(self):
        """Test that translate_file requires target language."""
        provider = LibreTranslateProvider()

        async def run_test():
            with self.assertRaises(TranslationException) as exc_info:
                await provider.translate_file(b"test content", "test.txt", source_lang="en", target_lang=None)
            return exc_info.exception

        exc = self._async_test(run_test())
        self.assertIn("Target language is required", exc.message)
        self.assertEqual(exc.api_error_code, "validation")

    def test_translate_file_downloads_bytes_from_translated_file_url(self):
        """Test that translate_file follows translatedFileUrl responses and returns downloaded bytes."""
        provider = LibreTranslateProvider(
            file_endpoint_url="http://localhost:5000/translate/file",
            max_retries=0,
            retry_backoff_seconds=0
        )

        responses = [
            FakeResponse({"translatedFileUrl": "http://localhost:5000/download_file/test-id"}),
            FakeResponse(b"translated file bytes", content_type="application/octet-stream"),
        ]

        def fake_urlopen(*args, **kwargs):
            return responses.pop(0)

        async def run_test():
            with patch("stores.translation.providers.LibreTranslateProvider.request.urlopen", side_effect=fake_urlopen):
                return await provider.translate_file(
                    b"test content",
                    "test.txt",
                    source_lang="en",
                    target_lang="ar"
                )

        translated_bytes = self._async_test(run_test())
        self.assertEqual(translated_bytes, b"translated file bytes")

    def test_translate_file_raises_when_translated_file_url_is_missing(self):
        """Test that translate_file rejects JSON responses without translatedFileUrl."""
        provider = LibreTranslateProvider(
            file_endpoint_url="http://localhost:5000/translate/file",
            max_retries=0,
            retry_backoff_seconds=0
        )

        async def run_test():
            with patch(
                "stores.translation.providers.LibreTranslateProvider.request.urlopen",
                return_value=FakeResponse({"status": "ok"})
            ):
                with self.assertRaises(TranslationException) as exc_info:
                    await provider.translate_file(
                        b"test content",
                        "test.txt",
                        source_lang="en",
                        target_lang="ar"
                    )
            return exc_info.exception

        exc = self._async_test(run_test())
        self.assertIn("translatedFileUrl", exc.message)
        self.assertEqual(exc.api_error_code, "invalid_response")

    def test_language_normalization(self):
        """Test that language codes are properly normalized."""
        provider = LibreTranslateProvider()

        # Test alias normalization
        self.assertEqual(provider.normalize_language("arabic"), "ar")
        self.assertEqual(provider.normalize_language("AR"), "ar")
        self.assertEqual(provider.normalize_language("english"), "en")
        self.assertEqual(provider.normalize_language("EN"), "en")
        self.assertEqual(provider.normalize_language("ar"), "ar")
        self.assertEqual(provider.normalize_language("en"), "en")

        # Test invalid language values
        with self.assertRaises(TranslationException) as exc_info:
            provider.normalize_language("null")
        self.assertEqual(exc_info.exception.api_error_code, "validation")

        # Test None returns fallback
        self.assertEqual(provider.normalize_language(None, "en"), "en")


if __name__ == "__main__":
    unittest.main()
