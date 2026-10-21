"""Comprehension, the listening decision and combining grading passes (PRD 6.3, 6.5, 7.2)."""

from collections.abc import Sequence
from dataclasses import dataclass

from .constants import (
    COMPREHENSION_CUT,
    ITEM_MAX_POINTS,
    ITEM_WEIGHT,
    LISTENING_THRESHOLD,
    RETELL_FULL_COVERAGE,
    RETELL_PASS_TOLERANCE,
    RETELL_SPREAD_LIMIT,
    RETELL_WEIGHT,
)


def weighted_credit(propositions: Sequence[tuple[int, float]]) -> float:
    """Sum of weight x credit over (weight, credit) pairs; weight 1 (detail) or 2 (core),
    credit 0, 0.5 or 1."""
    for weight, credit in propositions:
        if weight not in (1, 2) or credit not in (0, 0.5, 1):
            raise ValueError(f"bad proposition weight or credit: {weight}, {credit}")
    return sum(weight * credit for weight, credit in propositions)


def retell_coverage(credit: float, total_weight: int) -> float:
    """R_prop: full credit once the retell covers 60% of the total weight."""
    if total_weight <= 0 or not 0 <= credit <= total_weight:
        raise ValueError(f"credit {credit} is not within a total weight of {total_weight}")
    return min(1.0, credit / (RETELL_FULL_COVERAGE * total_weight))


def item_score(points: Sequence[int]) -> float:
    """Q_score: item points over the maximum. Works for any number of items."""
    if not points or any(p not in range(ITEM_MAX_POINTS + 1) for p in points):
        raise ValueError(f"item points must be 0, 1 or 2: {points}")
    return sum(points) / (ITEM_MAX_POINTS * len(points))


def comprehension_score(coverage: float, items: float) -> float:
    """RC on the read passage, LC on the listening passage, from 0 to 100, exact: the
    cuts compare the true score, and the report rounds it for display."""
    if not (0 <= coverage <= 1 and 0 <= items <= 1):
        raise ValueError("coverage and item score must be between 0 and 1")
    return 100 * (RETELL_WEIGHT * coverage + ITEM_WEIGHT * items)


@dataclass(frozen=True)
class Comprehension:
    score: float
    retell_coverage: float
    item_score: float


def comprehension(credit: float, total_weight: int, points: Sequence[int]) -> Comprehension:
    """The score with the coverage and item score it came from."""
    coverage = retell_coverage(credit, total_weight)
    items = item_score(points)
    return Comprehension(
        score=comprehension_score(coverage, items), retell_coverage=coverage, item_score=items
    )


def item_agreement(quick: Sequence[int], final: Sequence[int]) -> float:
    """Share of items where the quick and final points match (PRD 7.4 monitoring)."""
    if not quick or len(quick) != len(final):
        raise ValueError("quick and final points must cover the same items")
    return round(sum(q == f for q, f in zip(quick, final)) / len(quick), 2)


# ---- 6.5 listening module


@dataclass(frozen=True)
class ListeningOutcome:
    lc_used: bool
    flag: str | None


def run_listening_module(quick_rc: float) -> bool:
    """The one decision taken during the session, on the quick RC (PRD 7.4)."""
    return quick_rc < LISTENING_THRESHOLD


def listening_outcome(listening_module_run: bool, final_rc: float | None) -> ListeningOutcome:
    """Reconciles the in-session decision with the final RC. A reading stopped by the
    kindness rule has no RC, so its listening result is always used."""
    if final_rc is None:
        return ListeningOutcome(lc_used=listening_module_run, flag=None)
    if listening_module_run:
        if final_rc >= LISTENING_THRESHOLD:
            return ListeningOutcome(lc_used=False, flag="LC_NOT_USED")
        return ListeningOutcome(lc_used=True, flag=None)
    if final_rc < COMPREHENSION_CUT:
        return ListeningOutcome(lc_used=False, flag="LC_MISSED")
    return ListeningOutcome(lc_used=False, flag=None)


@dataclass(frozen=True)
class CombinedRetell:
    credit: float
    disagreement: bool


@dataclass(frozen=True)
class CombinedItems:
    points: tuple[int, ...]
    disagreement: bool


def retell_needs_third_pass(a: float, b: float) -> bool:
    return abs(a - b) > RETELL_PASS_TOLERANCE


def combine_retell_passes(a: float, b: float, c: float | None = None) -> CombinedRetell:
    """Weighted retell credit: the mean of two passes within 1.0 of each other, otherwise
    the median of three, a disagreement when the three still spread more than 2.0."""
    if not retell_needs_third_pass(a, b):
        return CombinedRetell(credit=(a + b) / 2, disagreement=False)
    if c is None:
        raise ValueError("the retell passes differ by more than 1.0; a third pass is needed")
    low, middle, high = sorted((a, b, c))
    return CombinedRetell(credit=middle, disagreement=high - low > RETELL_SPREAD_LIMIT)


def items_need_third_pass(a: Sequence[int], b: Sequence[int]) -> bool:
    _check_same_items(a, b)
    return list(a) != list(b)


def combine_item_passes(
    a: Sequence[int], b: Sequence[int], c: Sequence[int] | None = None
) -> CombinedItems:
    """Item points: where the passes differ, the majority of three. An item on which all
    three differ is a disagreement and takes the middle value."""
    if not items_need_third_pass(a, b):
        return CombinedItems(points=tuple(a), disagreement=False)
    if c is None:
        raise ValueError("the item passes differ; a third pass is needed")
    _check_same_items(a, c)
    points = [sorted(trio)[1] for trio in zip(a, b, c)]
    disagreement = any(len(set(trio)) == 3 for trio in zip(a, b, c))
    return CombinedItems(points=tuple(points), disagreement=disagreement)


def _check_same_items(a: Sequence[int], b: Sequence[int]) -> None:
    if len(a) != len(b):
        raise ValueError("grading passes must score the same items")
