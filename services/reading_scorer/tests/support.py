"""Test data and fakes for the Reading Scorer.

The reading is the fictional sess_demo_001 on the Market Day passage: the contract
fixtures in fixtures/contracts/ and the recorded transcripts in fixtures/ai/reading/.
The word times and pauses stand in for the CPU aligner and pause finder.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from aloai_events import MemoryPublisher
from aloai_store import MemoryStore
from services.reading_scorer.audio import Audio
from services.reading_scorer.scorer import Phase1Scorer
from services.reading_scorer.transcribers import FixtureReading

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "fixtures" / "contracts"
RECORDED = ROOT / "fixtures" / "ai" / "reading"
SESSION_ID = "sess_demo_001"
PASSAGE_ID = "bank_p3_market_day"
NOW = datetime(2026, 1, 15, 9, 3, 28, tzinfo=UTC)
READING = (
    "gs://aloai-dev-audio/3f2b9c1e-7d44-4c0b-8a52-0e6f1d9a7b10/READING/"
    "a1b2c3d4-0000-4000-8000-000000000001.flac"
)


def contract(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text())


TELEMETRY = contract("phase1_telemetry.sess_demo_001.json")
TIMES = [(event["start_ms"], event["end_ms"]) for event in TELEMETRY["word_events"]]
PAUSES = [(5330, 5780), (10760, 15180), (18430, 18610)]


def passage() -> dict:
    return contract("passage.bank_p3_market_day.json")


def seeded_store() -> MemoryStore:
    return MemoryStore({f"passages/{PASSAGE_ID}": passage()})


def recorded(**changes) -> dict:
    return {
        "session_id": SESSION_ID,
        "audio_uri": READING,
        "passage_id": PASSAGE_ID,
        "told_token_indices": [14],
    } | changes


class SilentAudio:
    def __init__(self) -> None:
        self.loaded: list[str] = []

    def load(self, uri: str) -> Audio:
        self.loaded.append(uri)
        return Audio(np.zeros(16_000, dtype=np.float32))


class RecordedTiming:
    """The word times and pauses measured on the recorded reading."""

    def __init__(self) -> None:
        self.aligned: list[list[str]] = []

    def word_times(self, audio: Audio, words: list[str]) -> list[tuple[int, int]]:
        self.aligned.append(list(words))
        return TIMES[: len(words)]

    def pauses(self, audio: Audio) -> list[tuple[int, int]]:
        return PAUSES


def scorer(store: MemoryStore, publisher: MemoryPublisher, **changes) -> Phase1Scorer:
    timing = RecordedTiming()
    parts = {
        "store": store,
        "publisher": publisher,
        "audio": SilentAudio(),
        "chirp": FixtureReading(RECORDED, "chirp"),
        "gemini": FixtureReading(RECORDED, "gemini"),
        "aligner": timing,
        "pause_finder": timing,
        "clock": lambda: NOW,
        "new_event_id": lambda: "6f1c2f0e-3a55-4a7e-9d1a-2b8c5e0a1004",
    }
    return Phase1Scorer(**(parts | changes))
