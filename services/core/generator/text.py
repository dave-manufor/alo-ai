"""Word handling shared by the estimator, the artifact builder and the gate.

clean_word follows the shared clip store's rule (PRD 4.5 G5) exactly, so the clip a token
points at is the clip the Session Agent plays: lowercase, NFC, punctuation stripped,
accents and inner apostrophes kept. tests/test_text.py checks it against the Session
Agent's copy until both move to a shared library.
"""

import re
import unicodedata

# Spelled the same, said differently (PRD 4.5 G5). The clip store needs an IPA for these;
# the generator keeps them out of stories instead (the gate's no_ambiguous_words).
HOMOGRAPHS = frozenset({"read", "live", "wind", "tear", "bow", "lead"})

_APOSTROPHES = {"’": "'", "‘": "'", "ʼ": "'"}
_EDGE = re.compile(r"^([^\w']*)(.*?)([^\w']*)$", re.DOTALL)


def clean_word(text: str) -> str:
    """Lowercase, NFC, punctuation and symbols stripped, inner apostrophes kept."""
    text = unicodedata.normalize("NFC", text)
    text = "".join(_APOSTROPHES.get(ch, ch) for ch in text).lower()
    kept = [
        ch
        for ch in text
        if ch == "'" or not unicodedata.category(ch).startswith(("P", "S", "Z", "C"))
    ]
    return unicodedata.normalize("NFC", "".join(kept)).strip("'")


def split_edges(token: str) -> tuple[str, str, str]:
    """A whitespace token as (leading punctuation, word, trailing punctuation)."""
    lead, core, trail = _EDGE.match(token).groups()
    return lead, core, trail


def words_of(sentences: list[str]) -> list[str]:
    """Every cleaned word of the sentences, in order (tokens with no letters are skipped)."""
    cleaned = (clean_word(token) for sentence in sentences for token in sentence.split())
    return [word for word in cleaned if word]
