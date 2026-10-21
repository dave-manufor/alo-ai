"""Where a passage's word clips live in the shared clip store (PRD 4.5 G5):

    gs://{bucket}/{voice_profile_id}/{tts_version}/words/{word_key}.mp3

word_key is the Session Agent's rule (services/session_agent/clips/keys.py): the cleaned
word, plus "~" and the IPA for a name, URL-encoded. tests/test_clips.py checks the two
agree on the bank passages. Making the missing clips comes with the G5 step.
"""

from urllib.parse import quote

from .artifact import ClipUri


def word_key(clean_text: str, ipa: str | None) -> str:
    return quote(clean_text if ipa is None else f"{clean_text}~{ipa}", safe="")


def word_clip_uri(
    bucket: str, voice_profile_id: str, tts_version: str, scheme: str = "gs"
) -> ClipUri:
    """scheme is gs on Google Cloud and az on Azure (the contracts accept both)."""
    prefix = f"{scheme}://{bucket}/{voice_profile_id}/{tts_version}/words"

    def uri(clean_text: str, ipa: str | None) -> str:
        return f"{prefix}/{word_key(clean_text, ipa)}.mp3"

    return uri
