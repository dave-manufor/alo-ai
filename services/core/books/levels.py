"""A publisher's own reading level, mapped to the Alo Reading Level (PRD 9.1).

Publishers level their books in their own words and none of them in ARL (1 to 12, about two a
primary class), so this table is a starting map, not a measurement. It is [CAL]: W3 signs it off,
every book is cross-checked by the text-level estimate (a book more than 2 levels from its mapped
ARL is held for a person, PRD 9.1), and the pilot replaces it with the trained model (PRD 9.2).
A publisher with no levels (Book Dash) needs the manifest to give the book's ARL with a reason.
"""

import re

# [CAL] PRD 9.1. African Storybook: 1 First words, 2 First sentences, 3 First paragraphs,
# 4 Longer paragraphs, 5 Read aloud. StoryWeaver: 1 Beginning to read, 2 Learning to read,
# 3 Reading independently, 4 Reading proficiently.
PUBLISHER_LEVELS: dict[str, dict[int, int]] = {
    "African Storybook": {1: 1, 2: 2, 3: 4, 4: 6, 5: 8},
    "StoryWeaver": {1: 2, 2: 4, 3: 6, 4: 8},
}
_LEVEL = re.compile(r"level\s*(\d+)", re.IGNORECASE)


def publisher_arl(publisher: str, publisher_level: str) -> int | None:
    """The ARL for a publisher's level ("Level 3", "Level 3: First paragraphs"), or None when
    this publisher or level has no mapping."""
    levels = PUBLISHER_LEVELS.get(publisher)
    found = _LEVEL.search(publisher_level)
    if levels is None or found is None:
        return None
    return levels.get(int(found.group(1)))
