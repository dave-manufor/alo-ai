"""Settings every Alo.ai service reads once from the environment.

Local shortcuts (ALO_ENV=local: emulators and recorded AI responses) must never run
on Cloud Run, which sets K_SERVICE.
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
    alo_env = env.get("ALO_ENV", "")
    if alo_env == "local" and env.get("K_SERVICE"):
        raise ConfigError("ALO_ENV=local is not allowed on Cloud Run (K_SERVICE is set)")
    ai_mode = env.get("AI_MODE", "fixtures")
    if ai_mode not in AI_MODES:
        raise ConfigError(f"AI_MODE={ai_mode!r} is not one of {sorted(AI_MODES)}")
    return Config(
        alo_env=alo_env,
        ai_mode=ai_mode,
        project=env.get("GOOGLE_CLOUD_PROJECT", "aloai-dev"),
        location=env.get("GOOGLE_CLOUD_LOCATION", "europe-west1"),
    )
