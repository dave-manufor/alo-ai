"""Who is calling: a guardian's Entra External ID access token (PRD 12).

The token's signature, expiry, issuer, audience and tenant are checked, and it must carry
the Account API's scope. The guardian is the token's object id (oid), never the email. The
verified claims are the only source of who the caller is: no route takes a guardian id from
the request.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Header

from .errors import AccountError
from .settings import AccountSettings

SigningKey = Callable[[str], Any]


@dataclass(frozen=True)
class Principal:
    guardian_id: str
    # None when the access token carries no email claim (it must be added to the API app
    # registration's optional claims); the routes that need an email refuse then.
    email: str | None
    sign_in_method: str  # "google" or "email_code", as apps/web/src/auth/entra.ts reads idp


class GuardianVerifier:
    def __init__(self, settings: AccountSettings, signing_key: SigningKey | None = None) -> None:
        self._settings = settings
        self._signing_key = signing_key or self._entra_key

    def _entra_key(self, token: str) -> Any:  # pragma: no cover - fetches Entra's keys
        client = jwt.PyJWKClient(self._settings.jwks_url)
        return client.get_signing_key_from_jwt(token).key

    def verify(self, token: str) -> Principal:
        settings = self._settings
        try:
            claims = jwt.decode(
                token,
                self._signing_key(token),
                algorithms=["RS256"],
                audience=settings.audience,
                issuer=settings.issuer,
                options={"require": ["exp", "iss", "aud"]},
            )
        except jwt.PyJWKClientConnectionError:
            raise AccountError(
                503, "AUTH_UNAVAILABLE", "Sign-in could not be checked just now.", retryable=True
            ) from None
        except jwt.PyJWTError:
            raise _refused() from None
        scopes = str(claims.get("scp", "")).split()
        guardian_id = claims.get("oid")
        if claims.get("tid") != settings.tenant_id or settings.scope not in scopes:
            raise _refused()
        if not isinstance(guardian_id, str) or not guardian_id:
            raise _refused()
        email = claims.get("email")
        google = "google" in str(claims.get("idp", "")).lower()
        return Principal(
            guardian_id=guardian_id,
            email=email if isinstance(email, str) and email else None,
            sign_in_method="google" if google else "email_code",
        )


def _refused() -> AccountError:
    return AccountError(401, "UNAUTHENTICATED", "Please sign in again.")


def current_guardian(verifier: GuardianVerifier) -> Callable[..., Principal]:
    """A FastAPI dependency: the verified guardian behind the Authorization header."""

    def dependency(authorization: Annotated[str | None, Header()] = None) -> Principal:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise _refused()
        return verifier.verify(token.strip())

    return dependency
