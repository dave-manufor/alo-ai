"""Mic-check levels while the child counts to five (PRD 4.1 step 0b, SDD 4).

Pure: fed 16-bit mono PCM. The audio is cut into 500 ms blocks; blocks above a
noise floor count as the child's voice. Too quiet: the voiced blocks' median RMS
is below -42 dBFS (or no voice at all). Too loud: more than 0.1% of samples clip.
"""

import math
import statistics
from array import array
from dataclasses import dataclass, field

from .machine.types import MicResult

SAMPLE_RATE = 16_000
BLOCK_SAMPLES = SAMPLE_RATE // 2  # 500 ms
QUIET_DBFS = -42.0  # [CAL] PRD 4.1
CLIP_FRACTION = 0.001  # [CAL] PRD 4.1: clipping above 0.1% of samples
VOICE_FLOOR_DBFS = -60.0  # below this a block is room noise, not the child
CLIP_LEVEL = 32_700


def block_dbfs(samples: array) -> float:
    if not samples:
        return -math.inf
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    return -math.inf if rms == 0 else 20 * math.log10(rms / 32_768)


@dataclass
class MicMeter:
    _pending: array = field(default_factory=lambda: array("h"))
    _levels: list[float] = field(default_factory=list)
    _samples: int = 0
    _clipped: int = 0

    def reset(self) -> None:
        """Start over, e.g. after the "closer" or "softer" retry prompt."""
        self._pending = array("h")
        self._levels.clear()
        self._samples = self._clipped = 0

    def feed(self, pcm: bytes) -> None:
        samples = array("h")
        samples.frombytes(pcm)
        self._samples += len(samples)
        self._clipped += sum(1 for s in samples if abs(s) >= CLIP_LEVEL)
        self._pending.extend(samples)
        while len(self._pending) >= BLOCK_SAMPLES:
            self._levels.append(block_dbfs(self._pending[:BLOCK_SAMPLES]))
            del self._pending[:BLOCK_SAMPLES]

    def result(self) -> MicResult:
        if self._samples and self._clipped / self._samples > CLIP_FRACTION:
            return MicResult(ok=False, problem="loud")
        voiced = [level for level in self._levels if level > VOICE_FLOOR_DBFS]
        if not voiced or statistics.median(voiced) < QUIET_DBFS:
            return MicResult(ok=False, problem="quiet")
        return MicResult(ok=True)
