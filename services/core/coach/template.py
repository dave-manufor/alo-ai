"""What the Reading Coach falls back on (PRD 3.1): a template summary and a default plan,
used when the Coach is off, fails, or writes a summary the guardrail refuses twice
(COACH_TEMPLATE_USED). Screening language only, and every number comes from the report.
The parent typed the child's name, so a summary the name makes fail the guardrail is
written without it.
"""

from aloai_guardrails import validate_parent_summary

from .library import activities_for

SOON_DAYS = 7
STANDARD_DAYS = 14

# What the check showed, said to the parent: a strength first, then what is growing.
STRENGTHS = {
    "ON_TRACK": "read accurately and understood the story well.",
    "UNDERSTANDS_BUILDING_WORD_READING": (
        "understood the story well, and is still building word reading."
    ),
    "DECODING_LIMITED": (
        "understood the story when it was read aloud, and is still building word reading."
    ),
    "FLUENT_NEEDS_LANGUAGE_SUPPORT": (
        "read the words well, and is still building understanding of stories."
    ),
    "NEEDS_SUPPORT_IN_BOTH": (
        "worked hard today, and is building both word reading and understanding of stories."
    ),
    "COMPREHENSION_STRATEGY_GAP": (
        "understood the story when listening, and is building understanding when reading alone."
    ),
}
RETRY_ADVICE = "Try another check in a quiet place, with the phone close to your child."
UNNAMED_CHILD = "Your child"


def next_check_days(report: dict) -> int:
    """PRD 3.1 step 5: 14 days, or 7 when the result was provisional or
    INSUFFICIENT_EVIDENCE."""
    profile = report["profile"]
    if profile["provisional"] or profile["code"] == "INSUFFICIENT_EVIDENCE":
        return SOON_DAYS
    return STANDARD_DAYS


def default_activities(report: dict) -> list[dict]:
    """The first three library activities for the profile at the reported level."""
    return activities_for(report["profile"]["code"], report["level"]["reported_arl"])[:3]


def template_summary(report: dict, first_name: str) -> str:
    summary = _summary(report, first_name)
    if validate_parent_summary(summary, report):
        return _summary(report, UNNAMED_CHILD)
    return summary


def _summary(report: dict, first_name: str) -> str:
    code = report["profile"]["code"]
    if code == "INSUFFICIENT_EVIDENCE":
        return f"{first_name}'s check today did not give us enough to go on. {RETRY_ADVICE}"
    sentences = [f"{first_name} {STRENGTHS[code]}"]
    wcpm = report["fluency"]["wcpm"]
    if wcpm is not None:
        sentences.append(f"{first_name} read {round(wcpm)} words correctly in a minute.")
    activities = default_activities(report)
    if activities:
        sentences.append(f"Try this at home: {activities[0]['title'].lower()}.")
    sentences.append("This was a short check, so think of it as a first look.")
    return " ".join(sentences)


def template_home_practice(report: dict) -> str:
    activities = default_activities(report)
    return activities[0]["text"] if activities else RETRY_ADVICE
