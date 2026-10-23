"""Test helpers: a signing key and tokens shaped like Entra External ID access tokens."""

import time
from datetime import UTC, datetime
from typing import Any

import jwt
from aloai_store import MemoryStore
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from services.account.auth import GuardianVerifier
from services.account.main import build_app
from services.account.settings import AccountSettings

TENANT = "11111111-2222-3333-4444-555555555555"
AUDIENCE = "99999999-8888-7777-6666-555555555555"
GUARDIAN = "guardian_demo_001"

SETTINGS = AccountSettings(
    tenant_id=TENANT,
    authority="https://aloai.ciamlogin.com",
    audience=AUDIENCE,
    scope="access_as_user",
    issuer=f"https://{TENANT}.ciamlogin.com/{TENANT}/v2.0",
    web_origin="https://web.example.test",
)

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def claims(**changes: Any) -> dict[str, Any]:
    """A valid guardian token's claims, with the given ones replaced (None removes one)."""
    now = int(time.time())
    base = {
        "iss": SETTINGS.issuer,
        "aud": AUDIENCE,
        "tid": TENANT,
        "oid": GUARDIAN,
        "scp": "access_as_user",
        "email": "guardian@example.com",
        "iat": now,
        "exp": now + 3600,
    }
    merged = base | changes
    return {name: value for name, value in merged.items() if value is not None}


def token(key: Any = KEY, **changes: Any) -> str:
    return jwt.encode(claims(**changes), key, algorithm="RS256")


def bearer(**changes: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(**changes)}"}


NOW = datetime(2026, 1, 15, 9, 0, 0, tzinfo=UTC)


def make_client(
    settings: AccountSettings = SETTINGS,
    store: MemoryStore | None = None,
    at=NOW,
    rooms=None,
    paystack=None,
):
    """(client, store): a fixed clock and ids child_1, consent_2, ... so tests can name them."""
    store = MemoryStore() if store is None else store
    counter = iter(range(1, 1000))

    def new_id(prefix: str) -> str:
        return f"{prefix}_{next(counter)}"

    verifier = GuardianVerifier(settings, signing_key=lambda _token: KEY.public_key())
    app = build_app(
        settings, store, verifier, now=lambda: at, new_id=new_id, rooms=rooms, paystack=paystack
    )
    return TestClient(app), store
