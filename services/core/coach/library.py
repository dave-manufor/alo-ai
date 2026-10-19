"""The activity library (PRD 3.1, 8): the only home activities the Reading Coach may
recommend, each tagged with the reader profiles and Alo Reading Levels it suits. The
Coach may personalise an activity's wording but never invents one."""

import json
from pathlib import Path

_LIBRARY = json.loads(Path(__file__).with_name("activities.json").read_text())
VERSION: str = _LIBRARY["version"]
ACTIVITIES: dict[str, dict] = {a["activity_id"]: a for a in _LIBRARY["activities"]}


def activities_for(profile: str, arl: int | None) -> list[dict]:
    """The activities for a profile, at a level when there is one."""
    return [
        activity
        for activity in ACTIVITIES.values()
        if profile in activity["profiles"]
        and (arl is None or activity["arl_min"] <= arl <= activity["arl_max"])
    ]
