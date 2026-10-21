"""Word times and pauses on CPU (PRD 5.1, 5.3): torchaudio's MMS_FA forced aligner and
Silero VAD v5, both baked into the scorer image. Needs PyTorch, so only the scorer
image imports this module.
"""

from collections.abc import Sequence
from itertools import pairwise

import torch
import torchaudio
from silero_vad import get_speech_timestamps, load_silero_vad

from .audio import SAMPLE_RATE, Audio, Span
from .words import normalize

SPEECH_THRESHOLD = 0.45  # [CAL] PRD 5.1: speech probability below this is silence
MIN_SILENCE_MS = 120  # [CAL] PRD 5.1


class MmsAligner:
    """Aligns the passage words read to the audio. A star token between words absorbs
    anything the child added, so every passage word gets a time even where misread."""

    def __init__(self) -> None:
        bundle = torchaudio.pipelines.MMS_FA
        self._model = bundle.get_model(with_star=True)
        self._tokenizer = bundle.get_tokenizer()
        self._aligner = bundle.get_aligner()

    def word_times(self, audio: Audio, words: Sequence[str]) -> list[Span]:
        waveform = torch.from_numpy(audio.samples).unsqueeze(0)
        with torch.inference_mode():
            emission, _ = self._model(waveform)
        transcript = [part for word in words for part in ("*", _letters(word))] + ["*"]
        spans = self._aligner(emission[0], self._tokenizer(transcript))[1::2]
        ms_per_frame = 1000 * waveform.size(1) / emission.size(1) / SAMPLE_RATE
        return [(round(s[0].start * ms_per_frame), round(s[-1].end * ms_per_frame)) for s in spans]


class SileroPauses:
    def __init__(self) -> None:
        self._model = load_silero_vad()

    def pauses(self, audio: Audio) -> list[Span]:
        speech = get_speech_timestamps(
            torch.from_numpy(audio.samples),
            self._model,
            sampling_rate=SAMPLE_RATE,
            threshold=SPEECH_THRESHOLD,
            min_silence_duration_ms=MIN_SILENCE_MS,
        )
        to_ms = 1000 / SAMPLE_RATE
        return [
            (round(before["end"] * to_ms), round(after["start"] * to_ms))
            for before, after in pairwise(speech)
        ]


def _letters(word: str) -> str:
    """MMS_FA reads lowercase a to z and the apostrophe; a word with none of them is a star."""
    letters = "".join(ch for ch in normalize(word) if "a" <= ch <= "z" or ch == "'")
    return letters or "*"
