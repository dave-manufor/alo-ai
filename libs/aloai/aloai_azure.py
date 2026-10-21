"""Azure OpenAI and Azure AI Speech for the services (CLOUD=azure).

What the services need from each, in small pieces the adapters take as arguments so tests
never reach Azure: the deployment for a role (deployment), the OpenAI client (open_openai),
the audio Speech takes (pcm16), what a recognition returns (words_from_result), the
speech a voice is asked to make (build_ssml), and the two Speech SDK calls that need the
network (recognize_words, synthesize).

The OpenAI client uses the v1 API of an Azure OpenAI resource ({endpoint}/openai/v1/), so
the deployment name is the `model` and no api-version is set. Speech uses the SDK: its
detailed output gives a word's confidence when the service computes one, and a word
without one is left unmarked (the grader marks only words it knows are unsure). Both reach
Azure with the managed identity; a key is for local runs and is refused when hosted
(aloai_env). recognize_words and synthesize are not exercised by tests, which is why they
are the only parts here marked `pragma: no cover`: check them against the real services
(the day-1 check in docs/adr/0001-azure-as-a-second-cloud.md) before relying on them.
"""

import io
import json
from collections.abc import Sequence
from xml.sax.saxutils import escape, quoteattr

from aloai_env import Config, require_setting

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"
SAMPLE_RATE = 16_000
RECOGNIZE_TIMEOUT_S = 120

Word = tuple[str, float | None]


def deployment(config: Config, role: str) -> str:
    """The Azure OpenAI deployment for a role: grader, quick, coach, embedding, transcribe."""
    deployments = config.openai_deployments or {}
    return require_setting(deployments.get(role), f"AZURE_OPENAI_DEPLOYMENTS[{role!r}]")


def open_openai(config: Config):  # pragma: no cover - builds a real client
    from openai import OpenAI

    if config.openai_key:
        credential = config.openai_key
    else:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        credential = get_bearer_token_provider(DefaultAzureCredential(), COGNITIVE_SCOPE)
    return OpenAI(base_url=openai_base_url(config), api_key=credential)


def openai_base_url(config: Config) -> str:
    return (
        require_setting(config.openai_endpoint, "AZURE_OPENAI_ENDPOINT").rstrip("/") + "/openai/v1/"
    )


def bearer_token(config: Config) -> str:  # pragma: no cover - asks Entra
    """A fresh credential for an OpenAI-compatible client that takes a string: the key for a
    local run, else the managed identity's access token (about an hour; build the client
    for each use rather than keeping it)."""
    if config.openai_key:
        return config.openai_key
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential().get_token(COGNITIVE_SCOPE).token


def pcm16(audio: bytes) -> bytes:
    """16-bit mono PCM from 16 kHz FLAC (the reading and response audio, PRD 5.1), the
    form Speech takes. Another sample rate is refused, as the reading track refuses it."""
    import soundfile

    samples, rate = soundfile.read(io.BytesIO(audio), dtype="int16", always_2d=True)
    if rate != SAMPLE_RATE:
        raise ValueError(f"the audio is {rate} Hz; the track is {SAMPLE_RATE} Hz")
    return samples.mean(axis=1).astype("int16").tobytes()


def words_from_result(raw: str) -> list[Word]:
    """The words of one recognition in Speech's detailed JSON, best alternative only, each
    with its confidence or None when the service gave none. Anything but a success is empty."""
    try:
        result = json.loads(raw)
        if result.get("RecognitionStatus") != "Success":
            return []
        best = (result.get("NBest") or [{}])[0]
        return [
            (word["Word"], word.get("Confidence"))
            for word in best.get("Words") or []
            if word.get("Word")
        ]
    except (TypeError, ValueError, AttributeError, KeyError):
        return []


def build_ssml(
    text: str,
    *,
    voice: str,
    locale: str,
    rate: str | None = None,
    ipa: tuple[str, str] | None = None,
) -> str:
    """SSML for a voice to say `text`. rate is a prosody rate such as "-10%". ipa is
    (word, pronunciation): that word in the text is spoken from the IPA pronunciation."""
    if ipa is None:
        body = escape(text)
    else:
        word, pronunciation = ipa
        before, found, after = text.partition(word)
        if not found:
            raise ValueError(f"{word!r} is not in {text!r}")
        body = (
            f'{escape(before)}<phoneme alphabet="ipa" ph={quoteattr(pronunciation)}>'
            f"{escape(word)}</phoneme>{escape(after)}"
        )
    if rate:
        body = f"<prosody rate={quoteattr(rate)}>{body}</prosody>"
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f"xml:lang={quoteattr(locale)}><voice name={quoteattr(voice)}>{body}</voice></speak>"
    )


def _speech_config(config: Config):  # pragma: no cover - builds a real client
    import azure.cognitiveservices.speech as speechsdk

    region = require_setting(config.speech_region, "AZURE_SPEECH_REGION")
    if config.speech_key:
        return speechsdk.SpeechConfig(subscription=config.speech_key, region=region)
    from azure.identity import DefaultAzureCredential

    resource = require_setting(config.speech_resource_id, "AZURE_SPEECH_RESOURCE_ID")
    token = DefaultAzureCredential().get_token(COGNITIVE_SCOPE).token
    return speechsdk.SpeechConfig(auth_token=f"aad#{resource}#{token}", region=region)


def recognize_words(
    config: Config, pcm: bytes, phrases: Sequence[str] = ()
) -> list[Word]:  # pragma: no cover - calls Azure AI Speech
    """Recognise 16 kHz mono PCM with the phrases (the passage's names) as hints. Returns
    every word of every utterance, in order."""
    import threading

    import azure.cognitiveservices.speech as speechsdk

    speech = _speech_config(config)
    speech.speech_recognition_language = config.speech_locale
    speech.output_format = speechsdk.OutputFormat.Detailed
    speech.request_word_level_timestamps()
    stream = speechsdk.audio.PushAudioInputStream(
        speechsdk.audio.AudioStreamFormat(
            samples_per_second=SAMPLE_RATE, bits_per_sample=16, channels=1
        )
    )
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech, audio_config=speechsdk.audio.AudioConfig(stream=stream)
    )
    if phrases:
        grammar = speechsdk.PhraseListGrammar.from_recognizer(recognizer)
        for phrase in phrases:
            grammar.addPhrase(phrase)
    words: list[Word] = []
    done = threading.Event()
    recognizer.recognized.connect(
        lambda event: words.extend(
            words_from_result(
                event.result.properties[speechsdk.PropertyId.SpeechServiceResponse_JsonResult]
            )
        )
    )
    recognizer.session_stopped.connect(lambda event: done.set())
    recognizer.canceled.connect(lambda event: done.set())
    recognizer.start_continuous_recognition()
    stream.write(pcm)
    stream.close()
    finished = done.wait(RECOGNIZE_TIMEOUT_S)
    recognizer.stop_continuous_recognition()
    if not finished:
        raise TimeoutError("Azure AI Speech did not finish recognising in time")
    return words


def synthesize(config: Config, ssml: str) -> bytes:  # pragma: no cover - calls Azure AI Speech
    """MP3 (16 kHz, mono) of the speech the SSML asks for."""
    import azure.cognitiveservices.speech as speechsdk

    speech = _speech_config(config)
    speech.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
    )
    result = (
        speechsdk.SpeechSynthesizer(speech_config=speech, audio_config=None)
        .speak_ssml_async(ssml)
        .get()
    )
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError(f"Azure AI Speech could not synthesise: {result.reason}")
    return result.audio_data
