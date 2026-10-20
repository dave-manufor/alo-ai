"""Bank passages for the session (PRD 4.5 fallback, 10.1).

Until the Passage Generator is live (day 3) every session reads a bank passage.
A READ passage names its listening passage (paired_listening_passage_id), so the
pair is loaded together. Locally the bank is a folder of passage JSON files
(fixtures/contracts/passage.*.json); in the cloud it is Firestore passages/{id}.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class PassageError(LookupError):
    pass


@dataclass(frozen=True)
class PassagePair:
    read: dict
    listening: dict | None


@dataclass(frozen=True)
class PassageBank:
    get: Callable[[str], dict | None]  # passage_id -> passage document

    def pair(self, passage_id: str) -> PassagePair:
        read = self._load(passage_id)
        if read["mode"] != "READ":
            raise PassageError(f"{passage_id} is a {read['mode']} passage, not READ")
        listening_id = read.get("paired_listening_passage_id")
        return PassagePair(read, self._load(listening_id) if listening_id else None)

    def _load(self, passage_id: str) -> dict:
        passage = self.get(passage_id)
        if passage is None:
            raise PassageError(f"no passage {passage_id}")
        return passage


def folder_bank(folder: Path) -> PassageBank:
    """A bank read from passage.*.json files, keyed by passage_id."""
    passages = {}
    for path in sorted(folder.glob("passage.*.json")):
        passage = json.loads(path.read_text())
        passages[passage["passage_id"]] = passage
    return PassageBank(passages.get)
