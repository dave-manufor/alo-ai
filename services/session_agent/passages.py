"""Bank passages for the session (PRD 4.5 fallback, 10.1).

The bank passage is the fallback when the Passage Generator gives no story; a generated
story is loaded the same way (both are passages/{id}). A READ passage names its listening
passage (paired_listening_passage_id), so the pair is loaded together. Both must fit the
session profile: the machine asks as many questions and listening items as the profile
says, and the Grader grades every item the passage has, so a passage with a different
count would make the report fail (PRD 4.5, passage.schema.json). Locally the bank is a
folder of passage JSON files (fixtures/contracts/passage.*.json); in the cloud it is
Firestore passages/{id}.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .machine.types import Profile


class PassageError(LookupError):
    pass


# The fallback READ passage for each session profile when the child's level is not known
# (PRD 4.5). BANK_PASSAGE_ID overrides it.
DEFAULT_BANK = {"standard": "bank_p3_school_garden", "demo": "bank_p3_market_day"}

# The STANDARD READ passages by ARL: one for each primary class's term 1 start level
# (2 x class - 1, PRD 6.7), Primary 1 to 5. Primary 6 (ARL 11) uses the nearest, ARL 9.
STANDARD_BANK = {
    1: "bank_p1_ada_and_the_dog",
    3: "bank_p2_lost_ball",
    5: "bank_p3_school_garden",
    7: "bank_p4_night_bus",
    9: "bank_p5_music_contest",
}


def passage_id_for_level(profile_name: str, level: int | None) -> str:
    """The READ passage to fall back on: the STANDARD one nearest the child's level (the
    easier one on a tie), or the profile's default when the level is not known. The demo
    profile has one passage."""
    if profile_name != "standard" or level is None:
        return DEFAULT_BANK[profile_name]
    return STANDARD_BANK[min(STANDARD_BANK, key=lambda arl: (abs(arl - level), arl))]


@dataclass(frozen=True)
class PassagePair:
    read: dict
    listening: dict | None


@dataclass(frozen=True)
class PassageBank:
    get: Callable[[str], dict | None]  # passage_id -> passage document

    def pair(self, passage_id: str, profile: Profile) -> PassagePair:
        read = self._load(passage_id)
        if read["mode"] != "READ":
            raise PassageError(f"{passage_id} is a {read['mode']} passage, not READ")
        _check_fits(read, profile, profile.n_questions)
        listening_id = read.get("paired_listening_passage_id")
        listening = self._load(listening_id) if listening_id else None
        if listening is not None:
            _check_fits(listening, profile, profile.n_listening_items)
        return PassagePair(read, listening)

    def _load(self, passage_id: str) -> dict:
        passage = self.get(passage_id)
        if passage is None:
            raise PassageError(f"no passage {passage_id}")
        return passage


def _check_fits(passage: dict, profile: Profile, n_items: int) -> None:
    length = passage.get("length_profile")
    if length != profile.name.upper():
        raise PassageError(
            f"{passage['passage_id']} is a {length} passage; this session is {profile.name}"
        )
    if len(passage["items"]) != n_items:
        raise PassageError(
            f"{passage['passage_id']} has {len(passage['items'])} items; "
            f"a {profile.name} session asks {n_items}"
        )


def folder_bank(folder: Path) -> PassageBank:
    """A bank read from passage.*.json files, keyed by passage_id."""
    passages = {}
    for path in sorted(folder.glob("passage.*.json")):
        passage = json.loads(path.read_text())
        passages[passage["passage_id"]] = passage
    return PassageBank(passages.get)
