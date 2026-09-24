"""Official Python SDK for the Texto SMS API."""

from .client import Texto
from .errors import (
    TextoApiError,
    TextoAuthenticationError,
    TextoConnectionError,
    TextoError,
    TextoInsufficientCreditsError,
    TextoInvalidRequestError,
    TextoNotFoundError,
    TextoPermissionError,
    TextoRateLimitError,
    TextoServerError,
)
from .webhooks import is_inbound_event, parse_webhook_event, verify_webhook_signature

__version__ = "1.0.0"

__all__ = [
    "Texto",
    "TextoError",
    "TextoApiError",
    "TextoAuthenticationError",
    "TextoPermissionError",
    "TextoInvalidRequestError",
    "TextoInsufficientCreditsError",
    "TextoNotFoundError",
    "TextoRateLimitError",
    "TextoServerError",
    "TextoConnectionError",
    "verify_webhook_signature",
    "parse_webhook_event",
    "is_inbound_event",
    "__version__",
]
