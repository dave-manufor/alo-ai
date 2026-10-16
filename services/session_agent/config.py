"""Session Agent settings, read once from the environment.

VOICE_MODE and SESSION_PROFILE are server settings set in Terraform (PRD 15.1);
the browser never chooses them. Local shortcuts (ALO_ENV=local) must never run
on Cloud Run, which sets K_SERVICE.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from .machine.profiles import PROFILES, VOICE_MODES

AI_MODES = ("fixtures", "live")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    alo_env: str
    ai_mode: str
    voice_mode: str
    session_profile: str


def _choice(env: Mapping[str, str], name: str, default: str, allowed) -> str:
    value = env.get(name, default)
    if value not in allowed:
        raise ConfigError(f"{name}={value!r} is not one of {sorted(allowed)}")
    return value


def load(env: Mapping[str, str]) -> Config:
    alo_env = env.get("ALO_ENV", "")
    if alo_env == "local" and env.get("K_SERVICE"):
        raise ConfigError("ALO_ENV=local is not allowed on Cloud Run (K_SERVICE is set)")
    return Config(
        alo_env=alo_env,
        ai_mode=_choice(env, "AI_MODE", "fixtures", AI_MODES),
        voice_mode=_choice(env, "VOICE_MODE", "cache_first", VOICE_MODES),
        session_profile=_choice(env, "SESSION_PROFILE", "standard", PROFILES),
    )
