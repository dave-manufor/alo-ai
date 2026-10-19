"""The reading audio, 16 kHz mono FLAC in Cloud Storage (PRD 5.1), and what is measured
from it: each passage word's time and the pauses between words.

GcsAudio reads Cloud Storage, or its emulator when STORAGE_EMULATOR_HOST is set. The
aligner and pause finder run on CPU in the scorer image (timing.py).
"""

import io
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import soundfile
from google.cloud import storage

SAMPLE_RATE = 16_000

Span = tuple[int, int]


@dataclass(frozen=True)
class Audio:
    samples: np.ndarray


class AudioSource(Protocol):
    def load(self, uri: str) -> Audio: ...


class Aligner(Protocol):
    def word_times(self, audio: Audio, words: Sequence[str]) -> list[Span]:
        """The start and end of each word, in milliseconds."""
        ...


class PauseFinder(Protocol):
    def pauses(self, audio: Audio) -> list[Span]:
        """The silent intervals between stretches of speech, in milliseconds."""
        ...


class GcsAudio:
    def __init__(self, client: storage.Client) -> None:
        self._client = client

    def load(self, uri: str) -> Audio:
        bucket, _, name = uri.removeprefix("gs://").partition("/")
        data = self._client.bucket(bucket).blob(name).download_as_bytes()
        samples, rate = soundfile.read(io.BytesIO(data), dtype="float32", always_2d=True)
        if rate != SAMPLE_RATE:
            raise ValueError(f"{uri} is {rate} Hz; the reading track is {SAMPLE_RATE} Hz")
        return Audio(samples.mean(axis=1))
