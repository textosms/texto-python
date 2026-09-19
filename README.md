# Texto SMS — Python SDK

Official Python SDK for the [Texto](https://texto.com.au) SMS API. Send SMS to
Australian and New Zealand numbers, read replies, and manage sub-accounts,
numbers, credits, API keys, webhooks and reporting.

## Install

```bash
pip install texto-sdk
```

Requires Python 3.8 or newer.

## Quick start

```python
import os
from texto import Texto

texto = Texto(api_key=os.environ["TEXTO_API_KEY"])

result = texto.send(to="+61400000000", message="Your booking is confirmed for 2pm.")
print(result["message_id"], result["credits_used"])
```

## Configuration

```python
texto = Texto(
    api_key="txt_...",
    timeout=30.0,      # seconds
    max_retries=2,     # retries for idempotent requests
)
```

`base_url` can be overridden, but only to point tests at a mock server or a
corporate proxy. The production API is always `https://api.texto.com.au`.

## Sending

```python
texto.send(
    to="0400000000",
    message="Hi Sam, your order has shipped.",
    sender="TEXTO",        # optional dedicated number or approved Sender ID
    link_tracking=True,     # optional per-message override
    campaign="Shipping",    # optional campaign name
)

texto.send_batch(
    message="Hi {name}, your appointment is {time}.",
    recipients=[
        {"phone": "0400000001", "merge_data": {"name": "Sam", "time": "2pm"}},
        {"phone": "0400000002", "merge_data": {"name": "Alex", "time": "3pm"}},
    ],
)

payload = texto.get_message(result["message_id"])
print(payload["delivery_receipt"])
```

## Replies and opt-outs

```python
inbox = texto.inbox(limit=50)
optouts = texto.optouts()
```

## Credits, accounts and numbers

```python
texto.balance()
texto.list_accounts()
sub = texto.create_account(business_name="Acme Pty Ltd", email="ops@acme.com.au")
texto.allocate_credits(sub["account_id"], 500)
texto.available_numbers(country="AU")
texto.purchase_number(label="Support line")
```

Account, team and group endpoints require account hierarchy to be enabled on
your Texto account.

## Reporting

```python
texto.report(from_="2026-01-01", to="2026-01-31", direction="outbound")
texto.group_report(from_="2026-01-01")
```

## Webhooks

```python
from flask import Flask, request
from texto import parse_webhook_event, is_inbound_event

app = Flask(__name__)

@app.post("/texto-webhook")
def texto_webhook():
    event = parse_webhook_event(
        request.get_data(),                      # raw body, not re-serialised
        request.headers.get("X-Texto-Signature"),
        os.environ["TEXTO_WEBHOOK_SECRET"],
    )
    if is_inbound_event(event):
        print("Reply from", event["from"], event["body"])
    else:
        print("Delivery status", event["delivery_receipt"])
    return "", 200
```

## Errors

```python
from texto import TextoInsufficientCreditsError, TextoRateLimitError

try:
    texto.send(to="0400000000", message="Hi")
except TextoInsufficientCreditsError as err:
    print("Top up:", err.credits_required)
except TextoRateLimitError as err:
    print("Retry after", err.retry_after)
```

Every API error subclasses `TextoApiError` with `status`, `code` and `body`.
Network failures and timeouts raise `TextoConnectionError`.

## Support

- API reference: https://texto.com.au/developers
- Email: support@texto.com.au

## License

MIT © Floop Pty Ltd trading as Texto
