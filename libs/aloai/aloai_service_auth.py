"""Who is calling a service, and the token a service calls with (SDD 12.1).

Not aloai_authz, which decides what an agent may do. This is service to service: on
Google Cloud an ID token signed by Google for a service account; on Azure an Entra access
token, issued to a managed identity for the callee's audience. A check takes the
Authorization header and answers yes or no. The network parts (Google's and Entra's
signing keys) are injected as `verify`, so tests never reach either.
"""

import functools
from collections.abc import Callable, Collection, Mapping
from typing import Any

from aloai_env import Config

ServiceCheck = Callable[[str | None], bool]
Verify = Callable[[str, str | None], Mapping[str, Any]]


def anyone(authorization: str | None) -> bool:
    """Off the cloud (emulators, tests) a call is not signed."""
    return True


def _bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ")


def google_caller(
    service_account: str, audience: str | None = None, verify: Verify | None = None
) -> ServiceCheck:
    """A check that a call carries a Google-signed ID token whose email is this service
    account, and whose audience is this endpoint's when one is given. Cloud Run IAM lets
    every invoker in, the Session Agent included, so this is what stops another caller
    posting a session.done."""

    def check(authorization: str | None) -> bool:
        token = _bearer(authorization)
        if token is None:
            return False
        try:
            claims = (verify or _google_claims)(token, audience)
        except ValueError:
            return False
        return claims.get("email") == service_account and claims.get("email_verified") is True

    return check


def entra_caller(
    audience: str,
    tenant_id: str,
    callers: Collection[str],
    verify: Verify | None = None,
) -> ServiceCheck:
    """A check that a call carries an Entra access token for this audience, from this
    tenant, issued to one of the callers (the object ids of the managed identities that may
    call this service)."""

    def check(authorization: str | None) -> bool:
        token = _bearer(authorization)
        if token is None:
            return False
        try:
            claims = (verify or _entra_claims(tenant_id))(token, audience)
        except ValueError:
            return False
        return (
            claims.get("aud") == audience
            and claims.get("tid") == tenant_id
            and claims.get("oid") in callers
        )

    return check


def _google_claims(
    token: str, audience: str | None
) -> Mapping[str, Any]:  # pragma: no cover - fetches Google's keys
    from google.auth.exceptions import GoogleAuthError
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    try:
        return id_token.verify_oauth2_token(token, Request(), audience=audience)
    except GoogleAuthError as error:
        raise ValueError(str(error)) from error


def _entra_claims(tenant_id: str) -> Verify:  # pragma: no cover - fetches Entra's keys
    import jwt

    keys = jwt.PyJWKClient(f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys")
    issuers = [
        f"https://sts.windows.net/{tenant_id}/",
        f"https://login.microsoftonline.com/{tenant_id}/v2.0",
    ]

    def verify(token: str, audience: str | None) -> Mapping[str, Any]:
        try:
            key = keys.get_signing_key_from_jwt(token).key
            return jwt.decode(token, key, algorithms=["RS256"], audience=audience, issuer=issuers)
        except jwt.PyJWTError as error:
            raise ValueError(str(error)) from error

    return verify


def service_token(config: Config, audience: str) -> str:  # pragma: no cover - asks the cloud
    """The token to call another service with: a Google ID token for the audience, or an
    Entra token for the audience's `/.default` scope, from the managed identity."""
    if config.cloud == "gcp":
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        return id_token.fetch_id_token(Request(), audience)
    return _azure_credential().get_token(f"{audience}/.default").token


@functools.cache
def _azure_credential():  # pragma: no cover - builds a real credential
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()
