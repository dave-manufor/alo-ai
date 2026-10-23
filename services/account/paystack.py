"""Paystack (PRD 11.1): the two calls this service makes to it, and the webhook signature.

The secret key is this service's alone (Key Vault, injected as PAYSTACK_SECRET_KEY) and is never
logged. Paystack stays in test mode: settings.py refuses a key that is not a test key (sk_test_)
unless PAYSTACK_LIVE is true. Every transaction is initialized here with the plan code, so the
browser can change neither the amount nor the plan (the plan's amount overrides the one sent).
"""

import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol

API = "https://api.paystack.co"
TIMEOUT_S = 10


class PaystackError(Exception):
    """Paystack did not answer, or did not answer with success. The message is a short reason,
    never Paystack's own text (which can echo the request)."""


class Paystack(Protocol):
    def initialize(
        self, *, email: str, plan: str, amount_kobo: int, reference: str, metadata: dict
    ) -> dict:
        """Transaction Initialize: {authorization_url, access_code, reference}."""
        ...

    def verify(self, reference: str) -> dict:
        """Verify Transaction: the transaction's data (status, reference, amount, currency,
        paid_at, plan, customer)."""
        ...


def signature_ok(secret: str, body: bytes, signature: str | None) -> bool:
    """x-paystack-signature is the HMAC-SHA512 of the raw body with the secret key."""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)


class PaystackApi:
    def __init__(self, secret_key: str, opener: Callable[..., Any] = urllib.request.urlopen):
        self._secret = secret_key
        self._open = opener

    def initialize(
        self, *, email: str, plan: str, amount_kobo: int, reference: str, metadata: dict
    ) -> dict:
        body = {
            "email": email,
            "plan": plan,
            "amount": amount_kobo,
            "reference": reference,
            "metadata": metadata,
            "channels": ["card"],  # a plan renews by card (or direct debit), not by USSD
        }
        return self._call("POST", "/transaction/initialize", body)

    def verify(self, reference: str) -> dict:
        return self._call("GET", f"/transaction/verify/{urllib.parse.quote(reference, safe='')}")

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        request = urllib.request.Request(
            API + path,
            data=None if body is None else json.dumps(body).encode(),
            method=method,
            headers={"Authorization": f"Bearer {self._secret}", "Content-Type": "application/json"},
        )
        try:
            with self._open(request, timeout=TIMEOUT_S) as response:
                reply = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise PaystackError(f"HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            raise PaystackError(type(error).__name__) from None
        if not isinstance(reply, dict) or reply.get("status") is not True:
            raise PaystackError("not a success")
        data = reply.get("data")
        if not isinstance(data, dict):
            raise PaystackError("no data")
        return data
