"""The reading audio, 16 kHz mono FLAC in object storage (PRD 5.1), and what is measured
from it: each passage word's time and the pauses between words.

BlobAudio reads whichever cloud's storage the Blobs given reads (gs:// or az://); GcsAudio is
it over Cloud Storage, or its emulator when STORAGE_EMULATOR_HOST is set. The
aligner and pause finder run on CPU in the scorer image (timing.py).
"""

import io
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import soundfile
from aloai_blobs import Blobs, GcsBlobs

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


class BlobAudio:
    """The reading audio from object storage, whichever cloud: any Blobs backend. A
    recording that is not there is a BlobNotFound (a LookupError), which the event handler
    parks, as it does a missing document."""

    def __init__(self, blobs: Blobs) -> None:
        self._blobs = blobs

    def load(self, uri: str) -> Audio:
        data = self._blobs.read(uri)
        samples, rate = soundfile.read(io.BytesIO(data), dtype="float32", always_2d=True)
        if rate != SAMPLE_RATE:
            raise ValueError(f"{uri} is {rate} Hz; the reading track is {SAMPLE_RATE} Hz")
        return Audio(samples.mean(axis=1))


class GcsAudio(BlobAudio):
    def __init__(self, client) -> None:  # a google.cloud.storage.Client
        super().__init__(GcsBlobs(client))
