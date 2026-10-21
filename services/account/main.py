"""Account service entry point: uvicorn services.account.main:create_app --factory.

The Account service (W1) owns guardians, children and consent, and is the only way the web
app reaches them. Every route but /healthz needs a guardian's Entra External ID access
token. It receives no Pub/Sub pushes and holds no AI. CLOUD picks the document store
(aloai_env); the entry refuses ALO_ENV=local on Cloud Run or Container Apps.
"""

import os
from collections.abc import Mapping
from typing import Annotated

import aloai_env
from aloai_store import Store, open_store
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import errors
from .auth import GuardianVerifier, Principal, current_guardian
from .settings import AccountSettings


def create_app(env: Mapping[str, str] | None = None) -> FastAPI:
    env = os.environ if env is None else env
    config = aloai_env.load(env, receives_pushes=False)
    settings = AccountSettings.from_env(env, hosted=config.hosted)
    return build_app(settings, open_store(config), GuardianVerifier(settings))


def build_app(settings: AccountSettings, store: Store, verifier: GuardianVerifier) -> FastAPI:
    app = FastAPI(title="Alo.ai Account")
    errors.install(app)
    if settings.web_origin:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.web_origin],
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    guardian = Depends(current_guardian(verifier))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/me")
    def me(principal: Annotated[Principal, guardian]) -> dict[str, str | None]:
        return {
            "guardian_id": principal.guardian_id,
            "email": principal.email,
            "sign_in_method": principal.sign_in_method,
        }

    return app
