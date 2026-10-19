"""Every score, band, level and profile in Alo.ai (PRD 6, 7.2, 8).

Pure functions: no I/O, no clock, no randomness and no model calls. The Reading
Scorer, the quick endpoint and final grading all call these, so a number means the
same thing wherever it appears. Models supply only proposition credits and item
points (PRD 7); everything else is computed here. Every constant, with the version
reports store, is in constants.py.
"""

from .comprehension import (
    CombinedItems,
    CombinedRetell,
    Comprehension,
    ListeningOutcome,
    combine_item_passes,
    combine_retell_passes,
    comprehension,
    comprehension_score,
    item_agreement,
    item_score,
    items_need_third_pass,
    listening_outcome,
    retell_coverage,
    retell_needs_third_pass,
    run_listening_module,
    weighted_credit,
)
from .constants import SCORING_MODULE, Band, ProfileCode
from .fluency import Fluency, fluency, word_reading_ok
from .levels import (
    ReportedLevel,
    approx_primary_class,
    book_band,
    level_confirmed,
    next_passage_level,
    performance_band,
    reported_level,
    start_arl,
)
from .profile import Profile, assign_profile

__all__ = [
    "SCORING_MODULE",
    "Band",
    "CombinedItems",
    "CombinedRetell",
    "Comprehension",
    "Fluency",
    "ListeningOutcome",
    "Profile",
    "ProfileCode",
    "ReportedLevel",
    "approx_primary_class",
    "assign_profile",
    "book_band",
    "combine_item_passes",
    "combine_retell_passes",
    "comprehension",
    "comprehension_score",
    "fluency",
    "item_agreement",
    "item_score",
    "items_need_third_pass",
    "level_confirmed",
    "listening_outcome",
    "next_passage_level",
    "performance_band",
    "reported_level",
    "retell_coverage",
    "retell_needs_third_pass",
    "run_listening_module",
    "start_arl",
    "weighted_credit",
    "word_reading_ok",
]
