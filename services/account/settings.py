"""What the Account service needs to check a guardian's Entra External ID token."""

from collections.abc import Mapping
from dataclasses import dataclass

from aloai_env import require_setting

DEFAULT_SCOPE = "access_as_user"


@dataclass(frozen=True)
class AccountSettings:
    tenant_id: str
    # The external tenant's sign-in address, such as https://aloai.ciamlogin.com (no path).
    authority: str
    # The Account API app registration's application (client) id: the token's aud.
    audience: str
    scope: str
    issuer: str
    # The one browser origin that may call the API. None only off the cloud.
    web_origin: str | None

    @property
    def jwks_url(self) -> str:
        return f"{self.authority}/{self.tenant_id}/discovery/v2.0/keys"

    @classmethod
    def from_env(cls, env: Mapping[str, str], *, hosted: bool) -> "AccountSettings":
        tenant_id = require_setting(env.get("ENTRA_TENANT_ID"), "ENTRA_TENANT_ID")
        authority = require_setting(env.get("ENTRA_AUTHORITY"), "ENTRA_AUTHORITY").rstrip("/")
        web_origin = env.get("WEB_ORIGIN") or None
        if hosted:
            require_setting(web_origin, "WEB_ORIGIN")
        return cls(
            tenant_id=tenant_id,
            authority=authority,
            audience=require_setting(env.get("ENTRA_API_AUDIENCE"), "ENTRA_API_AUDIENCE"),
            scope=env.get("ENTRA_API_SCOPE") or DEFAULT_SCOPE,
            issuer=env.get("ENTRA_ISSUER") or f"https://{tenant_id}.ciamlogin.com/{tenant_id}/v2.0",
            web_origin=web_origin.rstrip("/") if web_origin else None,
        )
