"""Checks on agent text before anyone sees it (PRD 3.1, SDD 8).

validate_parent_summary refuses a Reading Coach summary that states a number found in
neither the report nor the plan, uses a term that sounds like a diagnosis, or runs over
90 words. The Coach rewrites once; after a second failure the template summary is sent.
"""

import re
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

SUMMARY_MAX_WORDS = 90

BANNED_TERMS = re.compile(
    r"\b(diagnos\w*|dyslexi\w*|disorders?|behind|failing|slow learners?|hyperlexi\w*"
    r"|word callers?)\b",
    re.IGNORECASE,
)
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def validate_parent_summary(
    text: str, report: Mapping[str, Any], plan_numbers: Iterable[float] = ()
) -> list[str]:
    """What is wrong with the summary; an empty list means it may be sent."""
    problems = []
    words = len(text.split())
    if words > SUMMARY_MAX_WORDS:
        problems.append(f"{words} words; the limit is {SUMMARY_MAX_WORDS}")
    for term in sorted({match.lower() for match in BANNED_TERMS.findall(text)}):
        problems.append(f"uses {term!r}, which sounds like a diagnosis")
    allowed = traceable_numbers(report) | {float(number) for number in plan_numbers}
    for number in sorted(set(NUMBER.findall(text)), key=float):
        if float(number) not in allowed:
            problems.append(f"{number} is in neither the report nor the plan")
    return problems


def traceable_numbers(report: Mapping[str, Any]) -> set[float]:
    """Every number in the report, as stored and rounded the ways a sentence may say it:
    WCPM 93.8 may be said as 94, a share of 0.72 as 72%."""
    found: set[float] = set()
    for value in _numbers(report):
        found |= {float(value), float(round(value)), float(round(value, 1))}
        if 0 < value <= 1:
            found.add(float(round(100 * value)))
    return found


def _numbers(value: Any) -> Iterator[float]:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _numbers(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _numbers(item)
