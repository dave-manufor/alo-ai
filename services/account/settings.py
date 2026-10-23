"""What the Account service needs: the guardian's Entra External ID token check, the LiveKit
server, and Paystack (PRD 11.1)."""

from collections.abc import Mapping
from dataclasses import dataclass

from aloai_env import ConfigError, require_setting

DEFAULT_SCOPE = "access_as_user"
# The monthly plan's price (PRD 11.1: N1,500). Paystack takes the plan's own amount for a plan
# transaction; this is only the amount Transaction Initialize requires alongside it.
DEFAULT_PLAN_AMOUNT_KOBO = 150_000


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
    # The LiveKit server the session rooms are made on. Without all three, POST /v1/sessions
    # answers 503 (the other routes still work).
    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None
    # Paystack, test mode (PRD 11.1). Without the key and the plan code, the payment routes
    # answer 503 (the other routes still work). The key is never logged.
    paystack_secret_key: str | None = None
    paystack_plan_code: str | None = None
    plan_amount_kobo: int = DEFAULT_PLAN_AMOUNT_KOBO
    # A server setting (terraform.tfvars): true makes the weekly plan need the subscription (the
    # demo); false shows it to every guardian with a consented child (the mini-study).
    plans_need_subscription: bool = False

    @property
    def payments_on(self) -> bool:
        return bool(self.paystack_secret_key and self.paystack_plan_code)

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
            livekit_url=env.get("LIVEKIT_URL") or None,
            livekit_api_key=env.get("LIVEKIT_API_KEY") or None,
            livekit_api_secret=env.get("LIVEKIT_API_SECRET") or None,
            paystack_secret_key=_paystack_key(env),
            paystack_plan_code=env.get("PAYSTACK_PLAN_CODE") or None,
            plan_amount_kobo=int(env.get("PLAN_AMOUNT_KOBO") or DEFAULT_PLAN_AMOUNT_KOBO),
            plans_need_subscription=_flag(env, "PLANS_NEED_SUBSCRIPTION"),
        )


def _paystack_key(env: Mapping[str, str]) -> str | None:
    """PAYSTACK_SECRET_KEY, refused unless it is a test key (sk_test_): Paystack stays in test
    mode (AGENTS.md). PAYSTACK_LIVE=true is the deliberate switch for a live key."""
    key = env.get("PAYSTACK_SECRET_KEY") or None
    if key and not key.startswith("sk_test_") and env.get("PAYSTACK_LIVE") != "true":
        raise ConfigError(
            "PAYSTACK_SECRET_KEY is not a test key (sk_test_): Paystack stays in test mode"
        )
    return key


def _flag(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name) or "false"
    if value not in ("true", "false"):
        raise ConfigError(f"{name} must be true or false")
    return value == "true"
