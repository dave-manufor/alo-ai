"""Checks on agent text before anyone sees it (PRD 3.1, SDD 8).

validate_parent_summary refuses a Reading Coach summary that states a number found in
neither the report nor the plan, uses a term that sounds like a diagnosis, or runs over
90 words. The Coach rewrites once; after a second failure the template summary is sent.

A number may be written in digits or in words ("ninety-five"). Number words below ten
are not checked: they are everyday counts in the activities ("find three things"), and
no score or level is said that way.
"""

import re
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

SUMMARY_MAX_WORDS = 90

BANNED_TERMS = re.compile(
    r"\b(diagnos\w*|dyslexi\w*|disorders?|behind|failing|slow[\s-]+learners?|hyperlexi\w*"
    r"|word[\s-]+callers?)\b",
    re.IGNORECASE,
)
NUMBER = re.compile(r"\d+(?:\.\d+)?")
NUMBER_WORD_MIN = 10
UNITS = {
    word: value
    for value, word in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ]
    )
}
TENS = {
    word: 10 * value
    for value, word in enumerate(
        ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"], start=2
    )
}
WORD = re.compile(r"[a-z]+")
# Report fields that hold a share from 0 to 1, which a sentence may say as a percentage.
SHARES = frozenset({"retell_coverage", "item_score", "quick_vs_final_item_agreement"})
NOT_RESULTS = frozenset({"schema_version"})


def validate_parent_summary(
    text: str, report: Mapping[str, Any], plan_numbers: Iterable[float] = ()
) -> list[str]:
    """What is wrong with the summary; an empty list means it may be sent."""
    problems = []
    words = len(text.split())
    if words > SUMMARY_MAX_WORDS:
        problems.append(f"{words} words; the limit is {SUMMARY_MAX_WORDS}")
    terms = {re.sub(r"[\s-]+", " ", match.lower()) for match in BANNED_TERMS.findall(text)}
    for term in sorted(terms):
        problems.append(f"uses {term!r}, which sounds like a diagnosis")
    allowed = traceable_numbers(report) | {float(number) for number in plan_numbers}
    for number in sorted(set(NUMBER.findall(text)), key=float):
        if float(number) not in allowed:
            problems.append(f"{number} is in neither the report nor the plan")
    for said, value in sorted(number_words(text).items(), key=lambda pair: pair[1]):
        if value not in allowed:
            problems.append(f"{said!r} ({value:g}) is in neither the report nor the plan")
    return problems


def number_words(text: str) -> dict[str, float]:
    """Numbers of ten or more written in words, such as "ninety-five" or "one hundred",
    by how they were written."""
    found: dict[str, float] = {}
    run: list[str] = []
    for word in [*WORD.findall(text.lower()), ""]:
        if word in UNITS or word in TENS or word == "hundred" or (word == "and" and run):
            run.append(word)
            continue
        while run and run[-1] == "and":
            run.pop()
        if run and (value := _value(run)) >= NUMBER_WORD_MIN:
            found[" ".join(run)] = value
        run = []
    return found


def _value(words: list[str]) -> float:
    total = 0
    for word in words:
        if word == "hundred":
            total = (total or 1) * 100
        else:
            total += UNITS.get(word, TENS.get(word, 0))
    return float(total)


def traceable_numbers(report: Mapping[str, Any]) -> set[float]:
    """Every result in the report, as stored and rounded the ways a sentence may say it:
    WCPM 93.8 may be said as 94, and a share such as retell coverage 0.72 as 72%."""
    found: set[float] = set()
    for name, value in _numbers(report):
        found |= {float(value), float(round(value)), float(round(value, 1))}
        if name in SHARES:
            found.add(float(round(100 * value)))
    return found


def _numbers(value: Any, name: str = "") -> Iterator[tuple[str, float]]:
    if isinstance(value, bool) or name in NOT_RESULTS:
        return
    if isinstance(value, int | float):
        yield name, value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield from _numbers(item, key)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _numbers(item, name)
