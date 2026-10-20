"""Settings every Alo.ai service reads once from the environment.

Local shortcuts must never run on Cloud Run, which sets K_SERVICE in a service and
CLOUD_RUN_JOB in a job: ALO_ENV=local (emulators) is refused there, and so are the
recorded AI responses (AI_MODE=fixtures, the default), so a deployment that forgets
AI_MODE=live stops at start instead of replaying recordings. A Cloud Run service also
needs PUSH_SERVICE_ACCOUNT, the identity Pub/Sub pushes with, so its push route can turn
away any other caller (aloai_events.pushed_by).
"""

from collections.abc import Mapping
from dataclasses import dataclass

AI_MODES = ("fixtures", "live")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    alo_env: str
    ai_mode: str
    project: str
    location: str
    push_service_account: str | None = None


def load(env: Mapping[str, str]) -> Config:
    on_cloud_run = bool(env.get("K_SERVICE") or env.get("CLOUD_RUN_JOB"))
    alo_env = env.get("ALO_ENV", "")
    if alo_env == "local" and on_cloud_run:
        raise ConfigError("ALO_ENV=local is not allowed on Cloud Run")
    ai_mode = env.get("AI_MODE", "fixtures")
    if ai_mode not in AI_MODES:
        raise ConfigError(f"AI_MODE={ai_mode!r} is not one of {sorted(AI_MODES)}")
    if ai_mode == "fixtures" and on_cloud_run:
        raise ConfigError("recorded AI responses (AI_MODE=fixtures) are not allowed on Cloud Run")
    push_service_account = env.get("PUSH_SERVICE_ACCOUNT") or None
    if env.get("K_SERVICE") and push_service_account is None:
        raise ConfigError("PUSH_SERVICE_ACCOUNT must be set on a Cloud Run service")
    return Config(
        alo_env=alo_env,
        ai_mode=ai_mode,
        project=env.get("GOOGLE_CLOUD_PROJECT", "aloai-dev"),
        location=env.get("GOOGLE_CLOUD_LOCATION", "europe-west1"),
        push_service_account=push_service_account,
    )
