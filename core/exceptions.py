class ChartAPIError(Exception):
    """Raised when the external D1 chart API returns an error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthenticationError(ChartAPIError):
    """Raised when the D1 API rejects the token or token refresh fails."""


class LLMError(Exception):
    """Raised when the LLM (OpenAI) API fails."""
    
    def __init__(self, message: str, status_code: int | None = None):
            super().__init__(message)
            self.status_code = status_code


class PromptError(Exception):
    """Raised when a prompt file is missing or a placeholder has no value."""

class TransientError(Exception):
    """A temporary problem (network error, timeout, HTTP 429 / 5xx).
    Worth trying again. If it keeps happening, the caller turns it into its
    own error (ChartAPIError, LLMError ...)."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after