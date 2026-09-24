"""Helpers for verifying and parsing Texto webhooks."""

import hashlib
import hmac
import json
from typing import Any, Dict, Optional, Union


def verify_webhook_signature(
    payload: Union[str, bytes],
    signature: Optional[str],
    secret: str,
) -> bool:
    """Verify the ``X-Texto-Signature`` header against the raw request body.

    :param payload: Raw request body exactly as received (do not re-serialise).
    :param signature: Value of the ``X-Texto-Signature`` header, e.g. ``sha256=abc...``.
    :param secret: Signing secret shown when you rotated the webhook secret.
    """
    if not signature or not secret:
        return False
    provided = signature[7:] if signature.startswith("sha256=") else signature
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided, expected)


def parse_webhook_event(
    payload: Union[str, bytes],
    signature: Optional[str],
    secret: Optional[str],
) -> Dict[str, Any]:
    """Verify (when a secret is supplied) and decode a webhook body.

    Raises ``ValueError`` when the signature does not match.
    """
    if secret and not verify_webhook_signature(payload, signature, secret):
        raise ValueError("Texto webhook signature verification failed")
    return json.loads(payload)


def is_inbound_event(event: Dict[str, Any]) -> bool:
    """Return True when the event is an inbound (reply) message webhook."""
    return event.get("event") == "message.inbound"
