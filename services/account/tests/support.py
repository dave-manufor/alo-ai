"""Test helpers: a signing key and tokens shaped like Entra External ID access tokens."""

import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
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
