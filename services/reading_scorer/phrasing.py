"""Prosody phrasing from pauses, word times and the passage's boundaries (PRD 5.5).

A pause between two words is grammatical when the first word ends a phrase, clause or
sentence; a decoding pause when it sits next to an error or a told word; otherwise it
intrudes. Only eligible sentences count (declarative, at least 5 words, under 2 errors).
"""

from collections.abc import Sequence

import aloai_scoring as scoring

from .labels import ERRORS, WordLabel

Span = tuple[int, int]
CLOSERS = "\"'”’)]"  # what may follow a sentence's full stop, as in: "Thank you, Tunde."


def phrasing(
    tokens: Sequence[dict],
    labels: Sequence[WordLabel],
    times: Sequence[Span],
    pauses: Sequence[Span],
    accuracy_pct: float | None,
) -> scoring.Prosody:
    """tokens are the passage tokens; labels and times cover the words attempted."""
    read = tokens[: len(labels)]
    errors = {label.token_index for label in labels if label.label in ERRORS}
    eligible = _eligible_tokens(read, errors)
    intrusive = 0
    for gap in _pauses_after(times, pauses):
        if gap not in eligible or gap + 1 not in eligible:
            continue
        if read[gap]["syntactic_boundary_after"] != "NONE" or {gap, gap + 1} & errors:
            continue
        intrusive += 1
    chunks = sum(1 for i in eligible if read[i]["syntactic_boundary_after"] != "NONE")
    sentences = len({read[i]["sentence_index"] for i in eligible})
    return scoring.prosody(
        accuracy_pct=accuracy_pct,
        eligible_sentences=sentences,
        intrusive_pauses=intrusive,
        chunks=chunks,
    )


def _eligible_tokens(read: Sequence[dict], errors: set[int]) -> set[int]:
    """Tokens of the sentences read to the end that are eligible for phrasing."""
    sentences: dict[int, list[int]] = {}
    for index, token in enumerate(read):
        sentences.setdefault(token["sentence_index"], []).append(index)
    eligible: set[int] = set()
    for indices in sentences.values():
        last = read[indices[-1]]
        if last["syntactic_boundary_after"] != "TERMINAL":
            continue
        if scoring.sentence_eligible(
            words=len(indices),
            errors=len(errors.intersection(indices)),
            declarative=last["text"].rstrip(CLOSERS).endswith("."),
        ):
            eligible.update(indices)
    return eligible


def _pauses_after(times: Sequence[Span], pauses: Sequence[Span]) -> list[int]:
    """The word each pause follows: its middle falls between that word and the next.
    A pause inside a word, or before the first or after the last, is not a phrasing pause."""
    after = []
    for start, end in pauses:
        if end - start < scoring.PAUSE_MS:
            continue
        middle = (start + end) / 2
        for index in range(len(times) - 1):
            if times[index][1] <= middle <= times[index + 1][0]:
                after.append(index)
                break
    return after
