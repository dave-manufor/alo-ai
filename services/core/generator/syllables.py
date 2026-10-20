"""A syllable count good enough for the long-word share (PRD 4.5, 9.2).

Vowel groups, less a silent final e, a silent -ed and a silent -es. It is a heuristic:
it miscounts words like "area" (3 syllables, counted 2). The blueprint's limit is a share
of 3+ syllable words across a whole text, so single misses move the share very little.
"""

import re

_VOWEL_GROUPS = re.compile(r"[aeiouy]+")
_ES_SOUNDED = ("ses", "xes", "zes", "ches", "shes", "ces", "ges")


def count_syllables(word: str) -> int:
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    count = len(_VOWEL_GROUPS.findall(word))
    if word.endswith("e") and not word.endswith(("le", "ee", "ye")) and count > 1:
        count -= 1  # silent final e: "game", "stone"
    elif word.endswith("ed") and not word.endswith(("ted", "ded")) and count > 1:
        count -= 1  # "jumped", "played"
    elif word.endswith("es") and not word.endswith(_ES_SOUNDED) and count > 1:
        count -= 1  # "games", "stones"
    return max(count, 1)
