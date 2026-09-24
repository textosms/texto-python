"""Exception types raised by the Texto SDK."""

from typing import Any, Optional


class TextoError(Exception):
    """Base class for every error raised by the Texto SDK."""


class TextoApiError(TextoError):
    """Raised when the API returns a non-2xx response."""

    def __init__(
        self,
        message: str,
        status: int,
        body: Any = None,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.body = body
        self.code = code
        self.request_id = request_id


class TextoAuthenticationError(TextoApiError):
    """The API key is missing, invalid or revoked (401)."""


class TextoPermissionError(TextoApiError):
    """The account lacks access or the request was blocked (403)."""


class TextoInvalidRequestError(TextoApiError):
    """The request was rejected as invalid (400, 405, 409)."""


class TextoInsufficientCreditsError(TextoApiError):
    """The account has too few credits, or a card problem occurred (402)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        body = self.body if isinstance(self.body, dict) else {}
        self.credits_required = body.get("credits_required")
        self.credits_available = body.get("credits_available")


class TextoNotFoundError(TextoApiError):
    """The resource does not exist (404)."""


class TextoRateLimitError(TextoApiError):
    """The API is rate limiting the caller (429)."""

    def __init__(self, *args: Any, retry_after: Optional[float] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


class TextoServerError(TextoApiError):
    """The API returned a 5xx response."""


class TextoConnectionError(TextoError):
    """The request could not be completed (network failure or timeout)."""


def error_from_response(
    status: int,
    body: Any,
    request_id: Optional[str] = None,
    retry_after: Optional[float] = None,
) -> TextoApiError:
    record = body if isinstance(body, dict) else {}
    message = record.get("error") or f"Texto API request failed with status {status}"
    if not isinstance(message, str):
        message = f"Texto API request failed with status {status}"
    code = record.get("code") if isinstance(record.get("code"), str) else None

    kwargs = {"status": status, "body": body, "code": code, "request_id": request_id}

    if status == 401:
        return TextoAuthenticationError(message, **kwargs)
    if status == 402:
        return TextoInsufficientCreditsError(message, **kwargs)
    if status == 403:
        return TextoPermissionError(message, **kwargs)
    if status == 404:
        return TextoNotFoundError(message, **kwargs)
    if status == 429:
        return TextoRateLimitError(message, retry_after=retry_after, **kwargs)
    if status >= 500:
        return TextoServerError(message, **kwargs)
    return TextoInvalidRequestError(message, **kwargs)
