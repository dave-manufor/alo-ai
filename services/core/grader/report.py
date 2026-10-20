"""The ReadingReport (PRD 10.4, schemas/reading_report.schema.json).

Built from the session, the Phase 1 telemetry and the reconciled grading. Every
number comes from aloai_scoring, directly or through the telemetry it produced;
this module only arranges them. Book ids stay empty until book ranking (PRD 9.3)
is built, and parent_reporting stays null until the Reading Coach writes it.
"""

from dataclasses import dataclass
from datetime import datetime

import aloai_scoring as scoring
from aloai_events import iso_utc

from .asr import CHIRP_MODEL
from .models import GRADER_MODEL, QUICK_MODEL
from .prompts import PROMPT_VERSION

SCHEMA_VERSION = 1

VERSIONS = {
    "scoring_module": scoring.SCORING_MODULE,
    "quick_model": QUICK_MODEL,
    "grader_model": GRADER_MODEL,
    "grader_prompt": PROMPT_VERSION,
    "response_asr": CHIRP_MODEL,
}

# Plain words for parents (PRD 6.6, 8); screening language only.
PROFILE_TEXT = {
    "ON_TRACK": (
        "Reads accurately at a good pace and understands the story",
        "Try a higher level next time, with longer stories and fewer pictures.",
    ),
    "UNDERSTANDS_BUILDING_WORD_READING": (
        "Understands stories; reading the words is still developing",
        "Practise the sounds in the words that were hard today, and keep story questions at class level.",
    ),
    "DECODING_LIMITED": (
        "Understands stories when listening; reading the words gets in the way",
        "Practise sounding out words, and keep reading stories aloud together so learning continues.",
    ),
    "FLUENT_NEEDS_LANGUAGE_SUPPORT": (
        "Reads the words well; understanding the story is still developing",
        "Stop every few sentences to ask why things happened, and talk about new words.",
    ),
    "NEEDS_SUPPORT_IN_BOTH": (
        "Reading the words and understanding the story both need support",
        "Read a sentence aloud and let your child repeat it, and practise common words together.",
    ),
    "COMPREHENSION_STRATEGY_GAP": (
        "Understands stories when listening, but not yet when reading alone",
        "Read short parts and retell each one together, and check again within two weeks.",
    ),
    "INSUFFICIENT_EVIDENCE": (
        "This check did not give enough to go on",
        "Try another check in a quiet place, with the phone close to your child.",
    ),
}


@dataclass(frozen=True)
class ReportInputs:
    session_id: str
    session: dict
    child: dict
    passage: dict
    telemetry: dict
    grading: dict
    quick: dict | None
    previous_reported_arl: int | None
    now: datetime


def build_report(inputs: ReportInputs) -> dict:
    grading, telemetry, child = inputs.grading, inputs.telemetry, inputs.child
    rc = _comprehension(grading["read"])
    lc = _comprehension(grading["listen"])
    listening = scoring.listening_outcome(grading["listening_module_run"], rc.score if rc else None)
    flags = _flags(grading, telemetry, listening)
    d_ok = scoring.word_reading_ok(
        telemetry["accuracy_pct"], telemetry["wcpm"], child["primary_class"]
    )
    profile = scoring.assign_profile(
        flags=flags,
        reading_stopped_early=grading["reading_stopped_early"],
        d_ok=d_ok,
        rc=rc.score if rc else None,
        lc=lc.score if lc and listening.lc_used else None,
    )
    level = _level(inputs, rc, profile)
    primary_need, instructional_focus = PROFILE_TEXT[profile.code]
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": inputs.session_id,
        "child_id": inputs.session["child_id"],
        "guardian_id": child["guardian_id"],
        "timestamp_iso": iso_utc(inputs.now),
        "context": inputs.session["context"],
        "capture_mode": grading["capture_mode"],
        "session_settings": grading["session_settings"],
        "primary_class": child["primary_class"],
        "passage": {key: inputs.passage[key] for key in ("passage_id", "source", "title")}
        | {"topic_tags": inputs.passage.get("topic_tags", [])},
        "fluency": _fluency(telemetry, d_ok),
        "prosody": {
            key: telemetry["prosody"].get(key) for key in ("phrasing", "expression", "overall")
        }
        | {"reported": telemetry["prosody"]["reported"]},
        "comprehension": _comprehension_section(grading, inputs.quick, rc, lc, listening),
        "level": level,
        "profile": {
            "code": profile.code,
            "provisional": profile.provisional,
            "primary_need": primary_need,
            "instructional_focus": instructional_focus,
        },
        "recommendations": _recommendations(profile.code, level["reported_arl"]),
        "flags": flags,
        "parent_reporting": None,
        "versions": VERSIONS,
    }


def _comprehension(graded: dict | None) -> scoring.Comprehension | None:
    if graded is None:
        return None
    return scoring.comprehension(
        graded["weighted_credit"], graded["total_weight"], graded["item_points"]
    )


def _flags(grading: dict, telemetry: dict, listening: scoring.ListeningOutcome) -> list[str]:
    raised = [*grading["session_flags"], *telemetry["flags"]]
    if any(graded and graded["disagreement"] for graded in (grading["read"], grading["listen"])):
        raised.append("GRADER_DISAGREEMENT")
    if listening.flag:
        raised.append(listening.flag)
    return list(dict.fromkeys(raised))


def _shown(value: float | None, digits: int) -> float | None:
    """How the report shows an exact number; the decisions were taken on the exact one."""
    return None if value is None else round(value, digits)


def _fluency(telemetry: dict, d_ok: bool | None) -> dict:
    return {
        "accuracy_pct": _shown(telemetry["accuracy_pct"], 1),
        "wcpm": _shown(telemetry["wcpm"], 1),
        "words_attempted": telemetry["words_attempted"],
        "reading_seconds": telemetry["reading_seconds"],
        "self_correction_ratio": _shown(telemetry["self_correction_ratio"], 2),
        "word_reading_ok": d_ok,
    }


def _comprehension_section(
    grading: dict,
    quick: dict | None,
    rc: scoring.Comprehension | None,
    lc: scoring.Comprehension | None,
    listening: scoring.ListeningOutcome,
) -> dict:
    read = grading["read"]
    agreement = (
        scoring.item_agreement(quick["item_points"], read["item_points"])
        if quick and read
        else None
    )
    return {
        "reading_comprehension": _shown(rc.score, 1) if rc else None,
        "retell_coverage": _shown(rc.retell_coverage, 2) if rc else None,
        "item_score": _shown(rc.item_score, 2) if rc else None,
        "quick_reading_comprehension": _shown(quick["quick_rc"], 1) if quick else None,
        "listening_module_run": grading["listening_module_run"],
        "listening_comprehension": _shown(lc.score, 1) if lc else None,
        "listening_used": listening.lc_used and lc is not None,
        "quick_vs_final_item_agreement": agreement,
    }


def _level(
    inputs: ReportInputs, rc: scoring.Comprehension | None, profile: scoring.Profile
) -> dict:
    passage_arl = inputs.passage["arl_level"]
    band = scoring.performance_band(
        inputs.telemetry["accuracy_pct"],
        rc.score if rc else None,
        reading_stopped_early=inputs.grading["reading_stopped_early"],
    )
    reported = scoring.reported_level(passage_arl, band)
    return {
        "passage_arl": passage_arl,
        "band": band,
        "reported_arl": reported.arl if reported else None,
        "at_least": reported.at_least if reported else False,
        "confirmed": reported is not None
        and scoring.level_confirmed(inputs.previous_reported_arl, reported.arl),
        "next_passage_arl": scoring.next_passage_level(passage_arl, band),
        "approx_primary_class": (
            f"Primary {scoring.approx_primary_class(reported.arl)} (approximate, not normed)"
            if reported
            else None
        ),
    }


def _recommendations(profile_code: str, reported_arl: int | None) -> dict:
    band = scoring.book_band(profile_code, reported_arl)
    return {
        "arl_min": band[0] if band else None,
        "arl_max": band[1] if band else None,
        "book_ids": [],
    }
