"""Word keys for the shared clip store (PRD 4.5, G5).

Key = the word lowercased, punctuation stripped, Unicode NFC, accents kept
("Jàpá" and "Japa" are different words), URL-encoded. Names and a short list of
homographs add the IPA used, so a different pronunciation is a different clip.

One deliberate difference from the PRD wording: apostrophes inside a word are
kept ("we'll"), because stripping them would make it collide with "well" and
play the wrong clip.
"""

import unicodedata
from urllib.parse import quote

# Spelled the same, said differently (PRD 4.5). These always need an IPA.
HOMOGRAPHS = frozenset({"read", "live", "wind", "tear", "bow", "lead"})

_APOSTROPHES = {"’": "'", "‘": "'", "ʼ": "'"}


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


def word_key(text: str, ipa: str | None = None) -> str:
    """Key for one word's clip. Homographs and names must come with their IPA."""
    word = clean_word(text)
    if not word:
        raise ValueError(f"no word in {text!r}")
    if ipa is None and word in HOMOGRAPHS:
        raise ValueError(f"{word!r} is said more than one way; give the IPA used")
    return quote(word if ipa is None else f"{word}~{ipa}", safe="")
