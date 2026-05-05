from typing import Optional, Dict, Any


class TranslationException(Exception):
    """
    Single, minimal exception class for translation-related errors.

    Unified exception that captures all translation failure scenarios:
    - API errors (HTTP status codes)
    - Connection failures
    - Timeouts
    - Validation errors (invalid language codes)
    - Invalid responses

    Callers can inspect `api_error_code` to discriminate error types if needed.
    Extracts user-friendly messages from API responses automatically.
    """

    def __init__(
        self,
        message: str,
        api_error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize TranslationException.

        Args:
            message: User-friendly error message. May include extracted text from API response.
            api_error_code: Error code from API or error type identifier (e.g., '400', '500', 'timeout', 'connection').
                           Used for error discrimination by callers.
            details: Optional dictionary with raw error details from API response or context.

        Example:
            # API error with status code
            raise TranslationException(
                "LibreTranslate HTTP 400: Invalid language code 'xyz'",
                api_error_code="400",
                details={"status": 400, "error": "invalid_language"}
            )

            # Connection error
            raise TranslationException(
                "Connection failed: Connection refused",
                api_error_code="connection"
            )

            # Timeout error
            raise TranslationException(
                "Request timeout after 60 seconds",
                api_error_code="timeout"
            )
        """
        self.message = message
        self.api_error_code = api_error_code
        self.details = details or {}
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"TranslationException(message='{self.message}', "
            f"api_error_code='{self.api_error_code}')"
        )
