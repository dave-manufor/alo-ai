"""The consent a guardian gives for one child (PRD 12). The server writes the attestation
from this text, so a client cannot send its own. The same words are in the web app
(apps/web/src/account/store.ts, CONSENT_TEXT); a test keeps the two together."""

CONSENT_VERSION = "consent_v2_2026-10"
CONSENT_TEXT = (
    "I agree that Alo.ai can record my child reading aloud and answering questions, turn the "
    "recording into a written transcript, and use both to make a reading report for me. "
    "Recordings are kept for up to 90 days and then deleted. Transcripts and the report stay "
    "in my account until I ask for them to be deleted. Only my family and the Alo.ai study "
    "team can see them, and they are processed on secure servers in Europe. Alo.ai is a screening tool that helps us practise reading. My child can stop at "
    "any time, and I can ask for everything about my child to be deleted. Using recordings "
    "to help Alo.ai learn is a separate choice that stays off unless I turn it on."
)


def attestation_for(first_name: str, age: int) -> str:
    return f"I am the parent or guardian of {first_name}, aged {age}. {CONSENT_TEXT}"
