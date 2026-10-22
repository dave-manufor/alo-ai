"""The consent a guardian gives for one child (PRD 12). The server writes the attestation
from this text, so a client cannot send its own. The same words are in the web app
(apps/web/src/account/store.ts, CONSENT_TEXT); a test keeps the two together."""

CONSENT_VERSION = "consent_v1_2026-10"
CONSENT_TEXT = (
    "I agree that Alo.ai can record my child reading aloud, use the recording to make their "
    "reading report, and keep the audio for up to 90 days. Alo.ai is a screening tool that "
    "helps us practise reading."
)


def attestation_for(first_name: str, age: int) -> str:
    return f"I am the parent or guardian of {first_name}, aged {age}. {CONSENT_TEXT}"
