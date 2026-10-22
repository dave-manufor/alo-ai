"""Placing what a transcript heard against the passage (PRD 5.3).

Each transcript is aligned to the passage words by edit distance, so every passage word
gets the word heard in its place, or nothing when it was skipped, together with any
extra words heard just before it.

A child may stop anywhere (the kindness rule, the reading cap, "I'm done"), so the
passage words after the last one reached may cost nothing: they were not attempted. That
reading is kept only when the child said fewer words after the last one reached than the
passage had left. Saying as many or more means the child read on to the end, and those
words are misreadings of the passage words they stand for. A heard word only takes a
passage word's place cheaply when it looks like an attempt at it; one that is nothing
like it costs as much as a skip plus an extra word.

A child who stops near the end often says so ("I'm done", "stop"). Within the last few
passage words that would count as reading on, so a stop phrase at the end of what was
heard is dropped before aligning, unless its own words match the passage words they are
placed on (a passage that itself ends "...had to stop"). A polite word just before the
phrase ("Auntie, I'm done") goes with it, unless it is the passage word it is placed on
("ada met auntie", then "I'm done").
"""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

ATTEMPT_LIKENESS = 0.5  # [CAL] PRD 5.3: how alike a heard word must be to be a misreading
# The rules above, in the telemetry's model_versions: bump it when a change gives the same
# audio different word labels.
ALIGNMENT_VERSION = (
    "words_v3"  # v2: a stop phrase at the end is dropped (#34); v3: W3's single-transcript rule
)
# What the Session Agent hears as a stop, and the words a child may say with it
# (services/session_agent/intents.py; the scorer image doesn't carry the agent, so
# tests/test_words.py keeps the lists in step).
STOP_PHRASES = ("stop", "i want to stop", "i don't want to", "i'm done", "i am done", "no more")
POLITE = ("please", "auntie", "aunty")


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
    """Lowercase, without accents or punctuation, so "Jàpá," and "japa" match. A curly
    apostrophe counts as a straight one, so "we’ll" stays "we'll"."""
    decomposed = unicodedata.normalize("NFKD", word.lower().replace("’", "'").replace("‘", "'"))
    return "".join(ch for ch in decomposed if ch.isalnum() or ch == "'").strip("'")


def substitution(target: str, word: str) -> int:
    if target == word:
        return 0
    return 1 if SequenceMatcher(None, target, word).ratio() >= ATTEMPT_LIKENESS else 2


def align(passage: Sequence[str], heard: Sequence[Heard]) -> list[Placed]:
    """passage holds normalized words. Ties keep a word matched, and reach as far into
    the passage as the cheapest alignment allows."""
    words = [normalize(h.text) for h in heard]
    placed = _align(passage, heard, words)
    stop = _stop_at_end(words)
    if stop is None:
        return placed
    start, end = stop
    if _read(passage, placed, heard[start:end]):
        return placed  # the phrase is the passage's own ending
    while start and words[start - 1].replace("'", "") in POLITE:
        if _read(passage, placed, heard[start - 1 : start]):
            break  # "auntie" read as the passage, then "I'm done"
        start -= 1
    return align(passage, heard[:start])


def _stop_at_end(words: Sequence[str]) -> tuple[int, int] | None:
    """Where the stop phrase at the end of what was heard begins and ends, after any
    polite words that follow it ("I'm done, Auntie"), or None. Apostrophes are ignored,
    so "im done" is "i'm done"."""
    bare = [w.replace("'", "") for w in words]
    end = len(bare)
    while end and bare[end - 1] in POLITE:
        end -= 1
    phrases = (p.replace("'", "").split() for p in STOP_PHRASES)
    for phrase in sorted(phrases, key=len, reverse=True):  # "i want to stop" before "stop"
        start = end - len(phrase)
        if start >= 0 and bare[start:end] == phrase:
            return start, end
    return None


def _read(passage: Sequence[str], placed: Sequence[Placed], tail: Sequence[Heard]) -> bool:
    """Whether any of these heard words is the passage word it was placed on."""
    return any(
        p.heard is h and normalize(h.text) == word
        for p, word in zip(placed, passage, strict=True)
        for h in tail
    )


def _align(passage: Sequence[str], heard: Sequence[Heard], words: Sequence[str]) -> list[Placed]:
    rows, cols = len(passage), len(words)
    cost = [[i + j if i == 0 or j == 0 else 0 for j in range(cols + 1)] for i in range(rows + 1)]
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            cost[i][j] = min(
                cost[i - 1][j - 1] + substitution(passage[i - 1], words[j - 1]),
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
            )
    reached = min(range(rows + 1), key=lambda end: (cost[end][cols], -end))
    placed, before, said_after = _walk(passage, heard, words, cost, reached)
    if said_after >= rows - reached > 0:
        placed, before, _ = _walk(passage, heard, words, cost, rows)
    return [Placed(heard=placed[k], before=tuple(before[k])) for k in range(rows)]


def _walk(
    passage: Sequence[str],
    heard: Sequence[Heard],
    words: Sequence[str],
    cost: list[list[int]],
    end: int,
) -> tuple[list[Heard | None], list[list[str]], int]:
    """The alignment that ends at passage word `end`, and how many heard words came
    after the last passage word it reached."""
    rows = len(passage)
    placed: list[Heard | None] = [None] * rows
    before: list[list[str]] = [[] for _ in range(rows)]
    said_after = 0
    i, j = end, len(words)
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
            if i == end:
                said_after += 1
            j -= 1
    return placed, before, said_after
