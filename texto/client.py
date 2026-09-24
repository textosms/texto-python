"""Client for the Texto SMS API."""

import time
from typing import Any, Dict, List, Optional, Sequence, Union

import requests

from .errors import TextoConnectionError, error_from_response

DEFAULT_BASE_URL = "https://api.texto.com.au"
RETRYABLE_STATUSES = {408, 409, 429, 500, 502, 503, 504}
VERSION = "1.0.0"

JSON = Dict[str, Any]


def _clean(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


class Texto:
    """Client for the Texto SMS API.

    >>> texto = Texto(api_key="txt_...")
    >>> texto.send(to="+61400000000", message="Hello")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 2,
        session: Optional[requests.Session] = None,
    ) -> None:
        """
        :param api_key: Your Texto API key, beginning ``txt_``.
        :param base_url: Only override to point at a mock server or corporate
            proxy during testing. Production is always the Texto API.
        """
        if not api_key:
            raise ValueError("A Texto API key is required.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()

    # ── transport ───────────────────────────────────────────────────

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        """Perform a raw request. Exposed for endpoints not yet wrapped."""
        url = self.base_url + path
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": f"texto-python/{VERSION}",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        idempotent = method in ("GET", "PUT", "DELETE") or idempotency_key
        retries = self.max_retries if idempotent else 0

        last_error: Optional[Exception] = None
        for attempt in range(retries + 1):
            if attempt:
                time.sleep(min(2**attempt * 0.25, 4.0))
            try:
                response = self.session.request(
                    method,
                    url,
                    params=_clean(params or {}) or None,
                    json=json_body,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = TextoConnectionError(f"Request to {path} failed: {exc}")
                if attempt < retries:
                    continue
                raise last_error from exc

            try:
                body = response.json() if response.content else None
            except ValueError:
                body = {"error": response.text}

            if response.ok:
                return body

            if response.status_code in RETRYABLE_STATUSES and attempt < retries:
                last_error = error_from_response(response.status_code, body)
                continue

            retry_after = response.headers.get("Retry-After")
            raise error_from_response(
                response.status_code,
                body,
                response.headers.get("X-Request-Id"),
                float(retry_after) if retry_after and retry_after.isdigit() else None,
            )

        raise last_error or TextoConnectionError(f"Request to {path} failed")

    # ── status ──────────────────────────────────────────────────────

    def status(self) -> JSON:
        """Public health check. Does not consume credits."""
        return self.request("GET", "/status")

    # ── messaging ───────────────────────────────────────────────────

    def send(
        self,
        to: str,
        message: str,
        sender: Optional[str] = None,
        link_tracking: Optional[bool] = None,
        campaign: Optional[str] = None,
    ) -> JSON:
        """Send a single SMS.

        Include ``{{OptOutLink}}`` in the message to insert a unique
        per-recipient opt-out link (``texto.au/xxxxxx``, 15 characters). It
        always shortens, independent of link tracking, and is the recommended
        opt-out mechanism for Sender ID sends, where recipients cannot reply
        STOP.
        """
        return self.request(
            "POST",
            "/send",
            json_body=_clean(
                {
                    "to": to,
                    "message": message,
                    "sender": sender,
                    "link_tracking": link_tracking,
                    "campaign": campaign,
                }
            ),
        )

    def send_batch(
        self,
        recipients: Sequence[Union[str, Dict[str, Any]]],
        message: str,
        sender: Optional[str] = None,
        link_tracking: Optional[bool] = None,
        campaign: Optional[str] = None,
    ) -> JSON:
        """Send one message to up to 1,000 recipients, with optional merge data.

        Merge fields use ``{{key}}`` syntax; ``{{SendingNumber}}`` is always
        available. Include ``{{OptOutLink}}`` to insert a unique per-recipient
        opt-out link (always shortened to 15 characters) — recommended for
        Sender ID sends, where recipients cannot reply STOP.
        """
        return self.request(
            "POST",
            "/send-batch",
            json_body=_clean(
                {
                    "recipients": list(recipients),
                    "message": message,
                    "sender": sender,
                    "link_tracking": link_tracking,
                    "campaign": campaign,
                }
            ),
        )

    def get_message(self, message_id: str) -> JSON:
        """Fetch a message and its delivery receipt by id or idempotency key."""
        return self.request("GET", f"/message/{message_id}")

    def get_campaign(self, campaign_id: str, limit: Optional[int] = None, offset: Optional[int] = None) -> JSON:
        """Fetch a campaign with its per-message results."""
        return self.request("GET", f"/campaign/{campaign_id}", params={"limit": limit, "offset": offset})

    # ── inbox and opt-outs ──────────────────────────────────────────

    def inbox(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        from_: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> JSON:
        """List inbound (reply) messages."""
        return self.request(
            "GET",
            "/inbox",
            params={
                "limit": limit,
                "offset": offset,
                "from": from_,
                "date_from": date_from,
                "date_to": date_to,
            },
        )

    def optouts(self) -> List[JSON]:
        """List numbers that have opted out, including global opt-outs."""
        return self.request("GET", "/optouts")["optouts"]

    # ── credits ─────────────────────────────────────────────────────

    def balance(self) -> int:
        """Current credit balance for the calling account."""
        return self.request("GET", "/balance")["credits"]

    def account_balance(self, account_id: str) -> int:
        """Credit balance for a sub-account."""
        return self.request("GET", f"/account/{account_id}/balance")["credits"]

    def allocate_credits(self, account_id: str, amount: int) -> JSON:
        """Move credits from the calling account down to a sub-account."""
        return self.request("POST", f"/account/{account_id}/credits/allocate", json_body={"amount": amount})

    def recall_credits(self, account_id: str, amount: int) -> JSON:
        """Pull credits back from a sub-account."""
        return self.request("POST", f"/account/{account_id}/credits/recall", json_body={"amount": amount})

    # ── accounts ────────────────────────────────────────────────────

    def list_accounts(self) -> List[JSON]:
        """List the calling account and its sub-accounts."""
        return self.request("GET", "/accounts")["accounts"]

    def create_account(
        self,
        business_name: str,
        email: Optional[str] = None,
        daily_limit: Optional[int] = None,
        managed_by_parent: Optional[bool] = None,
        team_access_from_parent: Optional[bool] = None,
        optout_exempt: Optional[bool] = None,
        seed_credits: Optional[int] = None,
        inherit_parent_senders: Optional[bool] = None,
    ) -> JSON:
        """Create a sub-account. ``email`` is required unless managed by parent."""
        return self.request(
            "POST",
            "/accounts",
            json_body=_clean(
                {
                    "business_name": business_name,
                    "email": email,
                    "daily_limit": daily_limit,
                    "managed_by_parent": managed_by_parent,
                    "team_access_from_parent": team_access_from_parent,
                    "optout_exempt": optout_exempt,
                    "seed_credits": seed_credits,
                    "inherit_parent_senders": inherit_parent_senders,
                }
            ),
        )

    def get_account(self, account_id: str) -> JSON:
        """Fetch full detail for an account."""
        return self.request("GET", f"/account/{account_id}")["account"]

    def update_account(
        self,
        account_id: str,
        business_name: Optional[str] = None,
        daily_limit: Optional[int] = None,
        optout_exempt: Optional[bool] = None,
        team_access_from_parent: Optional[bool] = None,
        inherit_parent_senders: Optional[bool] = None,
    ) -> JSON:
        """Update a sub-account."""
        return self.request(
            "PATCH",
            f"/account/{account_id}",
            json_body=_clean(
                {
                    "business_name": business_name,
                    "daily_limit": daily_limit,
                    "optout_exempt": optout_exempt,
                    "team_access_from_parent": team_access_from_parent,
                    "inherit_parent_senders": inherit_parent_senders,
                }
            ),
        )

    def delete_account(self, account_id: str) -> JSON:
        """Schedule a sub-account for deletion."""
        return self.request("DELETE", f"/account/{account_id}")

    # ── users and access ────────────────────────────────────────────

    def list_team(self) -> List[JSON]:
        """Team members on the calling account."""
        return self.request("GET", "/team")["users"]

    def list_account_users(self, account_id: str) -> List[JSON]:
        """Team members on a specific account, including inherited ones."""
        return self.request("GET", f"/account/{account_id}/users")["users"]

    def invite_user(
        self,
        account_id: str,
        email: str,
        name: Optional[str] = None,
        can_send: Optional[bool] = None,
        can_billing: Optional[bool] = None,
    ) -> JSON:
        """Invite a person to an account."""
        return self.request(
            "POST",
            f"/account/{account_id}/users",
            json_body=_clean({"email": email, "name": name, "can_send": can_send, "can_billing": can_billing}),
        )

    def remove_user(self, account_id: str, member_id: str) -> JSON:
        """Remove a team member using the row id from the users list."""
        return self.request("DELETE", f"/account/{account_id}/users/{member_id}")

    def get_access(self, account_id: str) -> JSON:
        """Read parent-management and inherited-team settings."""
        return self.request("GET", f"/account/{account_id}/access")

    def set_access(
        self,
        account_id: str,
        managed_by_parent: Optional[bool] = None,
        team_access_from_parent: Optional[bool] = None,
    ) -> JSON:
        """Update parent-management and inherited-team settings."""
        return self.request(
            "PUT",
            f"/account/{account_id}/access",
            json_body=_clean(
                {
                    "managed_by_parent": managed_by_parent,
                    "team_access_from_parent": team_access_from_parent,
                }
            ),
        )

    # ── API keys ────────────────────────────────────────────────────

    def list_keys(self, account_id: str) -> List[JSON]:
        """List API keys on an account. Key values are never returned."""
        return self.request("GET", f"/account/{account_id}/keys")["keys"]

    def create_key(self, account_id: str, name: str) -> JSON:
        """Create an API key. The full value is returned once — store it securely."""
        return self.request("POST", f"/account/{account_id}/key", json_body={"name": name})

    def revoke_key(self, account_id: str, key_id: str) -> JSON:
        """Revoke an API key."""
        return self.request("DELETE", f"/account/{account_id}/key/{key_id}")

    # ── numbers ─────────────────────────────────────────────────────

    def list_numbers(self) -> List[JSON]:
        """Numbers owned by the calling account."""
        return self.request("GET", "/numbers")["numbers"]

    def list_group_numbers(self) -> List[JSON]:
        """Numbers across the calling account and all its sub-accounts."""
        return self.request("GET", "/numbers/group")["numbers"]

    def list_account_numbers(self, account_id: str) -> List[JSON]:
        """Numbers assigned to a specific account."""
        return self.request("GET", f"/account/{account_id}/numbers")["numbers"]

    def available_numbers(
        self,
        country: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> JSON:
        """Numbers currently available to purchase."""
        return self.request("GET", "/numbers/available", params={"country": country, "limit": limit, "offset": offset})

    def purchase_number(
        self,
        number: Optional[str] = None,
        label: Optional[str] = None,
        country: Optional[str] = None,
    ) -> JSON:
        """Purchase a dedicated number. Charges the card saved on the account."""
        return self.request(
            "POST",
            "/numbers/purchase",
            json_body=_clean({"number": number, "label": label, "country": country}),
        )

    def assign_numbers(self, account_id: str, numbers: Union[str, Sequence[str]]) -> JSON:
        """Assign parent-owned numbers to a sub-account."""
        return self.request("POST", f"/account/{account_id}/numbers/assign", json_body={"numbers": numbers})

    def recall_numbers(self, account_id: str, numbers: Union[str, Sequence[str]]) -> JSON:
        """Recall numbers from a sub-account."""
        return self.request("POST", f"/account/{account_id}/numbers/recall", json_body={"numbers": numbers})

    # ── webhooks ────────────────────────────────────────────────────

    def get_webhooks(self) -> JSON:
        """Read the configured delivery receipt and inbound webhooks."""
        return self.request("GET", "/webhooks")

    def set_delivery_webhook(self, url: str, enabled: Optional[bool] = None) -> JSON:
        """Create or update the delivery receipt webhook."""
        return self.request("PUT", "/webhooks/delivery", json_body=_clean({"url": url, "enabled": enabled}))[
            "delivery_receipt"
        ]

    def set_inbound_webhook(self, url: str, enabled: Optional[bool] = None) -> JSON:
        """Create or update the inbound message webhook."""
        return self.request("PUT", "/webhooks/inbound", json_body=_clean({"url": url, "enabled": enabled}))["inbound"]

    def rotate_delivery_secret(self) -> str:
        """Rotate the delivery receipt signing secret. Returned once."""
        return self.request("POST", "/webhooks/delivery")["secret"]

    def rotate_inbound_secret(self) -> str:
        """Rotate the inbound signing secret. Returned once."""
        return self.request("POST", "/webhooks/inbound")["secret"]

    # ── reporting ───────────────────────────────────────────────────

    def report(
        self,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        country: Optional[str] = None,
        campaign_id: Optional[str] = None,
        keyword: Optional[str] = None,
        number: Optional[str] = None,
    ) -> JSON:
        """Report for the calling account."""
        return self.request("GET", "/report", params=self._report_params(locals()))

    def account_report(self, account_id: str, **filters: Any) -> JSON:
        """Report for a specific account in the hierarchy."""
        return self.request("GET", f"/account/{account_id}/report", params=self._report_params(filters))

    def group_report(self, from_: Optional[str] = None, to: Optional[str] = None) -> JSON:
        """Report across the calling account and all its sub-accounts."""
        return self.request("GET", "/report/group", params={"from": from_, "to": to})

    @staticmethod
    def _report_params(values: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "from": values.get("from_"),
            "to": values.get("to"),
            "direction": values.get("direction"),
            "status": values.get("status"),
            "country": values.get("country"),
            "campaign_id": values.get("campaign_id"),
            "keyword": values.get("keyword"),
            "number": values.get("number"),
        }
