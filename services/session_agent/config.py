"""Session Agent settings, read once from the environment.

VOICE_MODE, SESSION_PROFILE and GENERATOR_ON are server settings set in Terraform
(PRD 15.1); the browser never chooses them. GENERATOR_ON stays false until the Writer +
Critic and tagger evaluation sets pass: then every session reads a bank passage. Local shortcuts (ALO_ENV=local) must never run
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
    generator_on: bool  # false: every session reads a bank passage (FALLBACK_PASSAGE)


FLAGS = {"true": True, "false": False}


def _flag(env: Mapping[str, str], name: str, default: str) -> bool:
    return FLAGS[_choice(env, name, default, FLAGS)]


def _choice(env: Mapping[str, str], name: str, default: str, allowed) -> str:
    value = env.get(name, default)
    if value not in allowed:
        raise ConfigError(f"{name}={value!r} is not one of {sorted(allowed)}")
    return value


@dataclass(frozen=True)
class WorkerSettings:
    """Where the worker's data goes. Names follow docs/LOCAL_DEV.md and Terraform."""

    project: str
    audio_bucket: str
    clips_bucket: str
    clips_base_url: str  # what the browser fetches clips from
    voice_profile_id: str
    tts_version: str
    core_url: str  # the Grader's grade:quick and the Passage Generator live in Core
    vertex_location: str  # the tagger's Gemini region (EU, PRD 12)
    bank_passage_id: str  # "" = the profile's default (passages.DEFAULT_BANK)
    bank_dir: str  # local only: a folder of passage.*.json files, instead of Firestore
    stt_language: str
    stt_location: str


def worker_settings(env: Mapping[str, str]) -> WorkerSettings:
    clips_bucket = env.get("CLIPS_BUCKET", "aloai-dev-clips")
    return WorkerSettings(
        project=env.get("GOOGLE_CLOUD_PROJECT", "aloai-dev"),
        audio_bucket=env.get("AUDIO_BUCKET", "aloai-dev-audio"),
        clips_bucket=clips_bucket,
        clips_base_url=env.get("CLIPS_BASE_URL", f"https://storage.googleapis.com/{clips_bucket}"),
        voice_profile_id=env.get("VOICE_PROFILE_ID", "vp_google_v1"),
        tts_version=env.get("TTS_VERSION", "v1"),
        core_url=env.get("CORE_URL", "http://localhost:8080"),
        vertex_location=env.get("GOOGLE_CLOUD_LOCATION", "europe-west1"),
        bank_passage_id=env.get("BANK_PASSAGE_ID", ""),
        bank_dir=env.get("BANK_DIR", ""),
        # Chirp 3 has no en-NG locale (PRD 1, decision 9); the day-3 benchmark picks one.
        stt_language=env.get("STT_LANGUAGE", "en-GB"),
        stt_location=env.get("STT_LOCATION", "eu"),  # Chirp 3: us or eu multi-region only
    )


def load(env: Mapping[str, str]) -> Config:
    alo_env = env.get("ALO_ENV", "")
    if alo_env == "local" and env.get("K_SERVICE"):
        raise ConfigError("ALO_ENV=local is not allowed on Cloud Run (K_SERVICE is set)")
    return Config(
        alo_env=alo_env,
        ai_mode=_choice(env, "AI_MODE", "fixtures", AI_MODES),
        voice_mode=_choice(env, "VOICE_MODE", "cache_first", VOICE_MODES),
        session_profile=_choice(env, "SESSION_PROFILE", "standard", PROFILES),
        generator_on=_flag(env, "GENERATOR_ON", "false"),
    )
