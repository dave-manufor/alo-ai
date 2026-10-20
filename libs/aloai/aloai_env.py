"""Settings every Alo.ai service reads once from the environment.

Local shortcuts must never run on Cloud Run, which sets K_SERVICE in a service and
CLOUD_RUN_JOB in a job: ALO_ENV=local (emulators) is refused there, and so are the
recorded AI responses (AI_MODE=fixtures, the default), so a deployment that forgets
AI_MODE=live stops at start instead of replaying recordings.
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
    return Config(
        alo_env=alo_env,
        ai_mode=ai_mode,
        project=env.get("GOOGLE_CLOUD_PROJECT", "aloai-dev"),
        location=env.get("GOOGLE_CLOUD_LOCATION", "europe-west1"),
    )
