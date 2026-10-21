"""The generator's content: the curated name list, the blocklist and the topic taxonomy
(PRD 4.5, 4.6). The files live in data/; each loader reads its file once."""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .names import Blocklist, Name, NameList
from .text import clean_word

DATA = Path(__file__).parent / "data"
GENRES = ("NARRATIVE", "EXPOSITORY")


@dataclass(frozen=True)
class Topic:
    tag: str
    description: str  # what the Writer is told the tag means
    factual: bool  # a factual tag can take an expository text (PRD 4.5 G2)


@dataclass(frozen=True)
class Taxonomy:
    topics: tuple[Topic, ...]

    @property
    def tags(self) -> tuple[str, ...]:
        return tuple(topic.tag for topic in self.topics)

    def topic(self, tag: str) -> Topic:
        for topic in self.topics:
            if topic.tag == tag:
                return topic
        raise KeyError(f"{tag!r} is not in the topic taxonomy")

    def genre(self, tags: list[str], hint: str | None = None) -> str:
        """NARRATIVE by default; EXPOSITORY when every tag is factual (PRD 4.5 G2).
        A genre_hint from the request wins."""
        if hint is not None:
            if hint not in GENRES:
                raise ValueError(f"genre must be one of {GENRES}, got {hint!r}")
            return hint
        if tags and all(self.topic(tag).factual for tag in tags):
            return "EXPOSITORY"
        return "NARRATIVE"


@cache
def names(path: Path = DATA / "names.json") -> NameList:
    entries = json.loads(path.read_text(encoding="utf-8"))["names"]
    return NameList(tuple(Name(e["text"], e["ipa"], e["kind"]) for e in entries))


@cache
def blocklist(path: Path = DATA / "blocklist.txt") -> Blocklist:
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    words = [line for line in lines if line and not line.startswith("#")]
    for word in words:
        if clean_word(word) != word:
            raise ValueError(f"blocklist entry {word!r} is not one cleaned word")
    return Blocklist(frozenset(words))


@cache
def taxonomy(path: Path = DATA / "taxonomy.json") -> Taxonomy:
    entries = json.loads(path.read_text(encoding="utf-8"))["tags"]
    return Taxonomy(tuple(Topic(e["tag"], e["description"], e["factual"]) for e in entries))
