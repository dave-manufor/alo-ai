"""Phase 1 telemetry (PRD 10.2, schemas/phase1_telemetry.schema.json), laid out from the
word labels, the aligned times and what aloai_scoring computed from them."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict

import aloai_scoring as scoring

from .labels import WordLabel

SCHEMA_VERSION = 1


def error_counts(labels: Sequence[WordLabel]) -> dict[str, int]:
    counted = Counter(label.label for label in labels)
    return {
        "substitution": counted["SUBSTITUTION"],
        "omission": counted["OMISSION"],
        "told": counted["TOLD"],
        "mispronunciation": counted["MISPRONUNCIATION"],
    }


def build_telemetry(
    *,
    session_id: str,
    passage: Mapping,
    labels: Sequence[WordLabel],
    times: Sequence[tuple[int, int]],
    fluency: scoring.Fluency,
    prosody: scoring.Prosody,
    model_versions: Mapping[str, str],
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "passage_id": passage["passage_id"],
        "passage_source": passage["source"],
        "reading_seconds": fluency.reading_seconds,
        "words_attempted": fluency.words_attempted,
        "words_correct": fluency.words_correct,
        "error_counts": error_counts(labels),
        "self_correction_count": sum(label.is_self_corrected for label in labels),
        "uncertain_count": sum(label.label == "UNCERTAIN" for label in labels),
        "accuracy_pct": fluency.accuracy_pct,
        "wcpm": fluency.wcpm,
        "self_correction_ratio": fluency.self_correction_ratio,
        "prosody": asdict(prosody),
        "word_events": [_event(label, times, index) for index, label in enumerate(labels)],
        "flags": list(fluency.flags),
        "model_versions": dict(model_versions),
    }


def _event(label: WordLabel, times: Sequence[tuple[int, int]], index: int) -> dict:
    start, end = times[index]
    return {
        "token_index": label.token_index,
        "target_word": label.target_word,
        "chirp_hypothesis": label.chirp.text if label.chirp else None,
        "gemini_hypothesis": label.gemini.text if label.gemini else None,
        "chirp_confidence": label.chirp.confidence if label.chirp else None,
        "start_ms": start,
        "end_ms": end,
        "label": label.label,
        "is_self_corrected": label.is_self_corrected,
        "pre_word_latency_ms": start - times[index - 1][1] if index else None,
    }
