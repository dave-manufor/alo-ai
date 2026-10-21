"""The reader profile (PRD 6.6) and which flags make a result provisional (6.8)."""

from collections.abc import Collection
from dataclasses import dataclass

from .constants import (
    BLOCKING_FLAGS,
    BORDER,
    COMPREHENSION_CUT,
    INFORMATIONAL_FLAGS,
    ProfileCode,
)


@dataclass(frozen=True)
class Profile:
    code: ProfileCode
    provisional: bool


def assign_profile(
    *,
    flags: Collection[str],
    reading_stopped_early: bool,
    d_ok: bool | None,
    rc: float | None,
    lc: float | None,
) -> Profile:
    """PRD 6.6. Pass lc only when the listening result is used (listening_outcome).
    Provisional near a cut, or with any flag that is not informational (PRD 6.8)."""
    code = _profile_code(set(flags), reading_stopped_early, d_ok, rc, lc)
    near_cut = any(
        score is not None and abs(score - COMPREHENSION_CUT) < BORDER for score in (rc, lc)
    )
    provisional = near_cut or any(flag not in INFORMATIONAL_FLAGS for flag in flags)
    return Profile(code=code, provisional=provisional)


def _profile_code(
    flags: set[str],
    reading_stopped_early: bool,
    d_ok: bool | None,
    rc: float | None,
    lc: float | None,
) -> ProfileCode:
    if flags & BLOCKING_FLAGS:
        return "INSUFFICIENT_EVIDENCE"
    if reading_stopped_early:
        if lc is None:
            return "INSUFFICIENT_EVIDENCE"
        return "DECODING_LIMITED" if lc >= COMPREHENSION_CUT else "NEEDS_SUPPORT_IN_BOTH"
    if d_ok is None or rc is None:
        return "INSUFFICIENT_EVIDENCE"
    if rc >= COMPREHENSION_CUT:
        return "ON_TRACK" if d_ok else "UNDERSTANDS_BUILDING_WORD_READING"
    if lc is None:
        return "INSUFFICIENT_EVIDENCE"
    if lc >= COMPREHENSION_CUT:
        return "COMPREHENSION_STRATEGY_GAP" if d_ok else "DECODING_LIMITED"
    return "FLUENT_NEEDS_LANGUAGE_SUPPORT" if d_ok else "NEEDS_SUPPORT_IN_BOTH"
