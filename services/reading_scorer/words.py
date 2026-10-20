"""Placing what a transcript heard against the passage (PRD 5.3).

Each transcript is aligned to the passage words by edit distance, so every passage word
gets the word heard in its place, or nothing when it was skipped, together with any
extra words heard just before it.

A child may stop anywhere (the kindness rule, the reading cap, "I'm done"), so the
passage words after the last one reached cost nothing: they were not attempted. A heard
word only takes a passage word's place cheaply when it looks like an attempt at it; one
that is nothing like it costs as much as a skip plus an extra word, so words said after
stopping are kept as extra words instead of taking the place of passage words.
"""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

ATTEMPT_LIKENESS = 0.5  # how alike a heard word must be to a passage word to be its misreading


@dataclass(frozen=True)
class Heard:
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class Placed:
    """What a transcript heard where one passage word belongs."""

    heard: Heard | None
    before: tuple[str, ...] = ()


def normalize(word: str) -> str:
    """Lowercase, without accents or punctuation, so "Jàpá," and "japa" match."""
    decomposed = unicodedata.normalize("NFKD", word.lower())
    return "".join(ch for ch in decomposed if ch.isalnum() or ch == "'").strip("'")


def substitution(target: str, word: str) -> int:
    if target == word:
        return 0
    return 1 if SequenceMatcher(None, target, word).ratio() >= ATTEMPT_LIKENESS else 2


def align(passage: Sequence[str], heard: Sequence[Heard]) -> list[Placed]:
    """passage holds normalized words. Ties keep a word matched, and reach as far into
    the passage as the cheapest alignment allows."""
    words = [normalize(h.text) for h in heard]
    rows, cols = len(passage), len(words)
    cost = [[i + j if i == 0 or j == 0 else 0 for j in range(cols + 1)] for i in range(rows + 1)]
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            cost[i][j] = min(
                cost[i - 1][j - 1] + substitution(passage[i - 1], words[j - 1]),
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
            )

    placed: list[Heard | None] = [None] * rows
    before: list[list[str]] = [[] for _ in range(rows)]
    i = min(range(rows + 1), key=lambda reached: (cost[reached][cols], -reached))
    j = cols
    while i > 0 or j > 0:
        diagonal = i > 0 and j > 0
        if diagonal and cost[i][j] == cost[i - 1][j - 1] + substitution(
            passage[i - 1], words[j - 1]
        ):
            placed[i - 1] = heard[j - 1]
            i, j = i - 1, j - 1
        elif i > 0 and cost[i][j] == cost[i - 1][j] + 1:
            i -= 1
        else:
            if i < rows:
                before[i].insert(0, words[j - 1])
            j -= 1
    return [Placed(heard=placed[k], before=tuple(before[k])) for k in range(rows)]
