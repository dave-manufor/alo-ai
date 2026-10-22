"""Phase 1 scoring on phase1.recorded (PRD 5.3, SDD 6).

Two transcripts, word labels where they agree, forced alignment for the times, and
fluency and phrasing from aloai_scoring. The telemetry is written once, to
sessions/{id}/phase1/telemetry, and phase1.scored follows so Core can assemble the
report. A redelivered event is not scored again; phase1.scored is sent again, and
report assembly ignores what it has already done.
"""

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import aloai_contracts
import aloai_scoring as scoring
from aloai_events import Publisher, envelope
from aloai_store import Store, require

from .audio import Aligner, AudioSource, PauseFinder
from .labels import label_words
from .phrasing import phrasing
from .telemetry import build_telemetry, error_counts
from .transcribers import CHIRP_MODEL, GEMINI_MODEL, PROMPT_VERSION, Transcriber
from .words import ALIGNMENT_VERSION, align, normalize

MODEL_VERSIONS = {
    "scoring_module": scoring.SCORING_MODULE,
    "chirp": CHIRP_MODEL,
    "gemini_transcription": GEMINI_MODEL,
    "transcription_prompt": PROMPT_VERSION,
    "alignment": "torchaudio-mms_fa",
    "word_alignment": ALIGNMENT_VERSION,
    "vad": "silero-vad-5",
}


# Single-transcript mode: no second transcription model was used, and the report says so.
SINGLE_TRANSCRIPT_VERSIONS = {
    **{
        k: v
        for k, v in MODEL_VERSIONS.items()
        if k not in ("gemini_transcription", "transcription_prompt")
    },
    "transcripts": "single",
}


def telemetry_path(session_id: str) -> str:
    return f"sessions/{session_id}/phase1/telemetry"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Phase1Scorer:
    store: Store
    publisher: Publisher
    audio: AudioSource
    chirp: Transcriber
    # None scores from the first transcript alone (SECOND_TRANSCRIPT=off; labels._label_single).
    gemini: Transcriber | None
    aligner: Aligner
    pause_finder: PauseFinder
    clock: Callable[[], datetime] = _now

    def handle(self, recorded: Mapping[str, Any]) -> None:
        """recorded is the data of a phase1.recorded event."""
        session_id = recorded["session_id"]
        path = telemetry_path(session_id)
        if self.store.get(path) is None:
            telemetry = self._score(recorded)
            aloai_contracts.PHASE1_TELEMETRY.validate(telemetry)
            self.store.set(path, telemetry)
        data = {"session_id": session_id, "telemetry_ref": path}
        self.publisher.publish(envelope("phase1.scored", session_id, data, now=self.clock()))

    def _score(self, recorded: Mapping[str, Any]) -> dict:
        passage = require(self.store, f"passages/{recorded['passage_id']}")
        tokens = passage["tokens"]
        uri = recorded["audio_uri"]
        audio = self.audio.load(uri)  # first, so audio not yet in the bucket costs no transcripts
        if self.gemini is None:
            heard_chirp, heard_gemini = self.chirp.heard(uri, passage), None
        else:
            with ThreadPoolExecutor(max_workers=2) as pool:
                chirp = pool.submit(self.chirp.heard, uri, passage)
                gemini = pool.submit(self.gemini.heard, uri, passage)
                heard_chirp, heard_gemini = chirp.result(), gemini.result()

        targets = [token["clean_text"] for token in tokens]
        words = [normalize(target) for target in targets]
        labels = label_words(
            targets,
            align(words, heard_chirp),
            None if heard_gemini is None else align(words, heard_gemini),
            set(recorded["told_token_indices"]),
        )
        times = self.aligner.word_times(audio, targets[: len(labels)]) if labels else []
        counts = error_counts(labels)
        told_first = 1 if labels and labels[0].label == "TOLD" else 0
        fluency = scoring.fluency(
            words_attempted=len(labels),
            reading_seconds=(times[-1][1] - times[0][0]) / 1000 if times else 0.0,
            substitutions=counts["substitution"],
            omissions=counts["omission"],
            told=counts["told"],
            told_waits=counts["told"] - told_first,
            mispronunciations=counts["mispronunciation"],
            self_corrections=sum(label.is_self_corrected for label in labels),
            uncertain=sum(label.label == "UNCERTAIN" for label in labels),
        )
        return build_telemetry(
            session_id=recorded["session_id"],
            passage=passage,
            labels=labels,
            times=times,
            fluency=fluency,
            prosody=phrasing(
                tokens, labels, times, self.pause_finder.pauses(audio), fluency.accuracy_pct
            ),
            model_versions=MODEL_VERSIONS if self.gemini else SINGLE_TRANSCRIPT_VERSIONS,
        )
