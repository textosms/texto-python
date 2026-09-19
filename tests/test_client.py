import hashlib
import hmac
import json

import pytest
import responses

from texto import (
    Texto,
    TextoAuthenticationError,
    TextoInsufficientCreditsError,
    verify_webhook_signature,
)

BASE = "https://api.texto.com.au"


@responses.activate
def test_send_uses_bearer_auth_and_snake_case_body():
    responses.add(responses.POST, f"{BASE}/send", json={"message_id": "m1", "credits_used": 1})
    texto = Texto(api_key="txt_test")

    result = texto.send(to="+61400000000", message="Hello", link_tracking=True)

    assert result["message_id"] == "m1"
    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer txt_test"
    assert json.loads(request.body) == {
        "to": "+61400000000",
        "message": "Hello",
        "link_tracking": True,
    }


@responses.activate
def test_report_filters_become_query_params():
    responses.add(responses.GET, f"{BASE}/report", json={"summary": {}})
    Texto(api_key="txt_test").report(from_="2026-01-01", direction="outbound")

    url = responses.calls[0].request.url
    assert "from=2026-01-01" in url and "direction=outbound" in url


@responses.activate
def test_authentication_error():
    responses.add(responses.GET, f"{BASE}/balance", json={"error": "Invalid API key"}, status=401)
    with pytest.raises(TextoAuthenticationError):
        Texto(api_key="txt_test").balance()


@responses.activate
def test_insufficient_credits_exposes_details():
    responses.add(
        responses.POST,
        f"{BASE}/send",
        json={"error": "Insufficient credits", "credits_required": 5, "credits_available": 1},
        status=402,
    )
    with pytest.raises(TextoInsufficientCreditsError) as exc:
        Texto(api_key="txt_test").send(to="0400000000", message="hi")
    assert exc.value.credits_required == 5


@responses.activate
def test_retries_retryable_get():
    responses.add(responses.GET, f"{BASE}/balance", json={"error": "boom"}, status=503)
    responses.add(responses.GET, f"{BASE}/balance", json={"credits": 10})

    assert Texto(api_key="txt_test", max_retries=1).balance() == 10
    assert len(responses.calls) == 2


@responses.activate
def test_does_not_retry_post():
    responses.add(responses.POST, f"{BASE}/send", json={"error": "boom"}, status=503)
    with pytest.raises(Exception):
        Texto(api_key="txt_test").send(to="0400000000", message="hi")
    assert len(responses.calls) == 1


def test_webhook_signature():
    body = json.dumps({"event": "message.inbound"})
    sig = "sha256=" + hmac.new(b"secret", body.encode(), hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, sig, "secret") is True
    assert verify_webhook_signature(body, sig, "other") is False
    assert verify_webhook_signature(body, None, "secret") is False
