"""The curated name list and the safety blocklist (PRD 4.5, 4.6).

Stories may use only the names on the list, each with the IPA the voice is given
(Chirp 3 HD accepts custom pronunciations, PRD 4.6). The data files come with the
content PR; this module is the shape the gate and the artifact builder read.
"""

from dataclasses import dataclass, field

from .text import clean_word

KINDS = ("PERSON", "PLACE", "KIN")


@dataclass(frozen=True)
class Name:
    text: str
    ipa: str
    kind: str  # PERSON, PLACE or KIN (Mama, Papa, Auntie)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"name kind must be one of {KINDS}, got {self.kind!r}")
        if not clean_word(self.text) or not self.ipa:
            raise ValueError(f"a name needs its text and its IPA: {self!r}")


@dataclass(frozen=True)
class NameList:
    entries: tuple[Name, ...] = ()
    _by_word: dict[str, Name] = field(init=False, repr=False, compare=False, default_factory=dict)

    def __post_init__(self) -> None:
        for name in self.entries:
            self._by_word[clean_word(name.text)] = name

    def get(self, word: str) -> Name | None:
        return self._by_word.get(clean_word(word))

    def __contains__(self, word: str) -> bool:
        return self.get(word) is not None


@dataclass(frozen=True)
class Blocklist:
    """Words that never appear in a story, a question or an answer (PRD 4.5 rules:
    no real people, brands, religion, politics, romance, violence or anything frightening)."""

    words: frozenset[str] = frozenset()

    def hits(self, text: str) -> list[str]:
        """The blocked words in the text, once each, in the order they appear."""
        found: list[str] = []
        for token in text.split():
            word = clean_word(token)
            if word in self.words and word not in found:
                found.append(word)
        return found
