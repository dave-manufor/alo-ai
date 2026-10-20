"""The rule-based text-level estimator (PRD 9.2, hackathon build).

Three features of a text, each mapped to a continuous ARL through the blueprint rows
(PRD 4.5); the estimate is their median, so a feature that is only a ceiling and sits far
below it (a text with no long words at all) does not pull the estimate down:

- mean sentence length: a row's limit is the top ARL of the row, so ARL = limit - 5;
- share of words with 3+ syllables: piecewise linear through the rows' limits;
- share of common words (wordfreq Zipf): each row asks for a share at its own threshold,
  so the estimate is where the text stops failing a row's requirement.

Names from the curated list are left out of the frequency and syllable features (PRD
4.5), but count as words in the sentence length. The mapping and its constants are [CAL]:
W3 signs them off, and the pilot replaces them with the trained model (PRD 9.2).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from wordfreq import zipf_frequency

from .blueprint import ROWS
from .names import NameList
from .syllables import count_syllables
from .text import clean_word

ARL_MIN, ARL_MAX = 1.0, 12.0
ZIPF_SLOPE = 20.0  # [CAL] ARLs per unit of common-word share beyond row 1's requirement
_TOPS = [float(row.arls[1]) for row in ROWS]  # 2, 4, ... 12


@dataclass(frozen=True)
class Features:
    words: int
    mean_sentence_length: float
    common_shares: tuple[float, ...]  # per blueprint row: share of words >= the row's Zipf
    long_share: float  # share of 3+ syllable words


@lru_cache(maxsize=4096)
def _zipf(word: str) -> float:
    return zipf_frequency(word, "en")


def features(sentences: Sequence[str], names: NameList) -> Features:
    if not sentences:
        raise ValueError("no sentences")
    tokens = [clean_word(t) for sentence in sentences for t in sentence.split()]
    tokens = [token for token in tokens if token]
    if not tokens:
        raise ValueError("no words")
    plain = [token for token in tokens if token not in names] or tokens
    return Features(
        words=len(tokens),
        mean_sentence_length=len(tokens) / len(sentences),
        common_shares=tuple(
            sum(_zipf(w) >= row.zipf_threshold for w in plain) / len(plain) for row in ROWS
        ),
        long_share=sum(count_syllables(w) >= 3 for w in plain) / len(plain),
    )


def _interpolate(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    """Piecewise linear through (xs, ys), continuing the end segments' slopes."""
    segment = 0
    while segment < len(xs) - 2 and x > xs[segment + 1]:
        segment += 1
    x0, x1, y0, y1 = xs[segment], xs[segment + 1], ys[segment], ys[segment + 1]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def _common_words_arl(shares: Sequence[float]) -> float:
    margins = [share - row.zipf_share for share, row in zip(shares, ROWS, strict=True)]
    for index, margin in enumerate(margins):
        if margin >= 0:
            if index == 0:
                return _TOPS[0] - margin * ZIPF_SLOPE  # easier than row 1's requirement
            below = margins[index - 1]
            return _TOPS[index - 1] + (_TOPS[index] - _TOPS[index - 1]) * -below / (margin - below)
    return _TOPS[-1] - margins[-1] * ZIPF_SLOPE  # harder than the last row allows


def estimate_arl(found: Features) -> float:
    """The estimated ARL, 1 to 12, to two decimals."""
    by_length = _interpolate(found.mean_sentence_length, [r.max_mean_sentence for r in ROWS], _TOPS)
    by_long_words = _interpolate(found.long_share, [r.max_long_share for r in ROWS], _TOPS)
    by_common_words = _common_words_arl(found.common_shares)
    clamped = sorted(
        min(max(estimate, ARL_MIN), ARL_MAX)
        for estimate in (by_length, by_long_words, by_common_words)
    )
    return round(clamped[1], 2)  # the median: a limit that is not near (no long words) is ignored
