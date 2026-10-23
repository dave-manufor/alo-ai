"""What the agent heard, in numbers, so a session that heard nothing can be explained.

Pure, and for logs only: it never decides anything and never holds a word. Counts frames,
voice-detector starts and ends (and how many started while a clip was playing, which is
Kemi's own voice coming back through the child's microphone), speech-to-text results (and
how many were empty or errors), and the input level in 100 ms blocks per turn.
"""

import statistics
from array import array
from dataclasses import dataclass, field

from .mic_check import block_dbfs

SAMPLE_RATE = 16_000
BLOCK_SAMPLES = SAMPLE_RATE // 10  # 100 ms
SILENT_DBFS = -120.0  # stands in for -inf so a median can be taken
VOICED_DBFS = -60.0  # the mic check's own floor: below this a block is room noise


@dataclass
class AudioStats:
    frames: int = 0
    first_frame_ms: int | None = None
    vad_starts: int = 0
    vad_ends: int = 0
    vad_starts_during_clip: int = 0
    stt_interim: int = 0
    stt_final: int = 0
    stt_empty: int = 0
    stt_errors: int = 0
    # A pipeline task that stopped, by name: the exception class, or "ended" if it just returned.
    stopped: dict[str, str] = field(default_factory=dict)
    _pending: array = field(default_factory=lambda: array("h"))
    _levels: list[float] = field(default_factory=list)

    def frame(self, pcm: bytes, now_ms: int) -> None:
        if self.first_frame_ms is None:
            self.first_frame_ms = now_ms
        self.frames += 1
        samples = array("h")
        samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
        self._pending.extend(samples)
        while len(self._pending) >= BLOCK_SAMPLES:
            level = block_dbfs(self._pending[:BLOCK_SAMPLES])
            self._levels.append(max(level, SILENT_DBFS))
            del self._pending[:BLOCK_SAMPLES]

    def vad_started(self, clip_playing: bool) -> None:
        self.vad_starts += 1
        if clip_playing:
            self.vad_starts_during_clip += 1

    def vad_ended(self) -> None:
        self.vad_ends += 1

    def transcript(self, text: str, *, final: bool) -> None:
        if not text.strip():
            self.stt_empty += 1
        elif final:
            self.stt_final += 1
        else:
            self.stt_interim += 1

    def stt_error(self) -> None:
        self.stt_errors += 1

    def task_stopped(self, name: str, how: str) -> None:
        self.stopped[name] = how

    def end_turn(self) -> str:
        """The input level over the turn that just ended, then start a new one."""
        levels, self._levels = self._levels, []
        self._pending = array("h")
        if not levels:
            return "level none (no audio in this turn)"
        ordered = sorted(levels)
        p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
        voiced = sum(1 for level in levels if level > VOICED_DBFS)
        return (
            f"level max {max(levels):.0f} median {statistics.median(levels):.0f} "
            f"p95 {p95:.0f} dBFS, {voiced}/{len(levels)} blocks above {VOICED_DBFS:.0f}"
        )

    def line(self) -> str:
        first = "none" if self.first_frame_ms is None else f"{self.first_frame_ms} ms"
        stopped = ", ".join(f"{name}: {how}" for name, how in sorted(self.stopped.items()))
        return (
            f"audio frames {self.frames} (first {first}); "
            f"vad starts {self.vad_starts} ends {self.vad_ends} "
            f"during clip {self.vad_starts_during_clip}; "
            f"stt interim {self.stt_interim} final {self.stt_final} "
            f"empty {self.stt_empty} errors {self.stt_errors}"
            + (f"; stopped: {stopped}" if stopped else "")
        )
