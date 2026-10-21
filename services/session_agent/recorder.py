"""Per-turn recording: 16 kHz mono FLAC, independent of Gemini Live (PRD 5, SDD 4).

The child's audio is the only input to grading, so every turn is recorded from the
microphone track itself. The FLAC is written to the turn's audio_uri when the
turn stops; `upload` decides how (in the worker: in a thread, to Cloud Storage).
"""

import io
from collections.abc import Callable

import numpy as np
import soundfile

from .recording import Turn

SAMPLE_RATE = 16_000


def encode_flac(pcm: bytes) -> bytes:
    samples = np.frombuffer(pcm, dtype=np.int16)
    out = io.BytesIO()
    soundfile.write(out, samples, SAMPLE_RATE, format="FLAC", subtype="PCM_16")
    return out.getvalue()


def object_name(audio_uri: str) -> tuple[str, str]:
    """gs://bucket/path or az://container/path -> (bucket, path)."""
    bucket, _, name = audio_uri.partition("://")[2].partition("/")
    return bucket, name


class FlacRecorder:
    def __init__(self, upload: Callable[[str, bytes], None]) -> None:
        """upload(audio_uri, flac_bytes)."""
        self._upload = upload
        self._turn: Turn | None = None
        self._pcm = bytearray()

    def start(self, turn: Turn) -> None:
        self._turn, self._pcm = turn, bytearray()

    def feed(self, pcm: bytes) -> None:
        if self._turn is not None:
            self._pcm.extend(pcm)

    def stop(self) -> None:
        if self._turn is None:
            return
        turn, pcm = self._turn, bytes(self._pcm)
        self._turn, self._pcm = None, bytearray()
        self._upload(turn.audio_uri, encode_flac(pcm))
