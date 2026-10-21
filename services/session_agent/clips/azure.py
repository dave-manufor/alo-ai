"""The text-to-speech call for "That word is X." clips on Azure (CLOUD=azure).

seed_words takes `synthesize(text, ipa)` and returns the MP3 for the sentence. This makes
that function from an Azure voice: the sentence is SSML for the voice, and a name or
homograph with an IPA is spoken from it (SSML `phoneme`). Use a new VOICE_PROFILE_ID for
an Azure voice (the clip store keeps each voice's clips apart, SDD 6), so Google and Azure
clips can sit side by side and the browser plays the ones the service's profile names.
"""

from collections.abc import Callable

from aloai_azure import build_ssml

from .prompts import WORD_CLIP_TEXT


def line_synthesizer(
    synthesize: Callable[[str], bytes], *, voice: str, locale: str
) -> Callable[[str], bytes]:
    """The speech for a whole line (a fixed prompt, a question, the listening story):
    `synthesize` takes SSML and returns MP3, as for word_synthesizer."""

    def make(text: str) -> bytes:
        return synthesize(build_ssml(text, voice=voice, locale=locale))

    return make


def word_synthesizer(
    synthesize: Callable[[str], bytes], *, voice: str, locale: str
) -> Callable[[str, str | None], bytes]:
    """`synthesize` takes SSML and returns MP3 (aloai_azure.synthesize with the settings
    bound); voice is an Azure voice such as en-NG-EzinneNeural."""

    def make(text: str, ipa: str | None) -> bytes:
        sentence = WORD_CLIP_TEXT.format(word=text)
        pronunciation = (text, ipa) if ipa else None
        return synthesize(build_ssml(sentence, voice=voice, locale=locale, ipa=pronunciation))

    return make
