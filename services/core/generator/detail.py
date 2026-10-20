"""The safe detail (PRD 4.5 G1): a common noun the child's interest chat produced.

The Session Agent's tagger proposes it; Core checks it again before it reaches the
Writer, because the child's own words must never get through unchecked. A detail is kept
only if it is one or two lowercase words, ends in a common noun (not a name), is common
enough for the level, is not on the blocklist, and is not on the name list.
"""

import re

from spacy.language import Language
from wordfreq import zipf_frequency

from .names import Blocklist, NameList
from .text import clean_word

PATTERN = re.compile(r"^[a-z]{2,20}( [a-z]{2,20})?$")  # same as passage_generate_request
MIN_ZIPF = 3.0  # [CAL] common enough for a P1 to P6 reader to know
NOUN_TAGS = frozenset({"NOUN", "PROPN"})


def safe_detail(
    detail: str | None, nlp: Language, names: NameList, blocklist: Blocklist
) -> str | None:
    """The detail to give the Writer, or None to drop it."""
    if detail is None:
        return None
    detail = " ".join(detail.lower().split())
    if not PATTERN.match(detail):
        return None
    words = detail.split()
    if any(word in names or blocklist.hits(word) for word in words):
        return None
    if any(zipf_frequency(clean_word(word), "en") < MIN_ZIPF for word in words):
        return None
    doc = nlp(f"I like the {detail}.")
    # A lowercase common word after "the" is sometimes tagged PROPN (parser noise on a
    # two-word phrase); the name list and the frequency check above already keep real
    # names out, so what this must reject is an adjective, a verb, an adverb and so on.
    if doc[3 + len(words) - 1].pos_ not in NOUN_TAGS:
        return None
    return detail
