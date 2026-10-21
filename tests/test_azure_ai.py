"""Tests for the Azure OpenAI and Azure AI Speech helpers in libs/aloai (CLOUD=azure): the
settings, the audio Speech takes, what a recognition returns and the speech a voice is
asked to make. Nothing here reaches Azure; the two Speech SDK calls are not tested (see the
module docstring of aloai_azure)."""

import io
import json
import xml.etree.ElementTree as ET

import aloai_env
import numpy as np
import pytest
import soundfile
from aloai_azure import (
    build_ssml,
    deployment,
    openai_base_url,
    pcm16,
    words_from_result,
)

SSML = "{http://www.w3.org/2001/10/synthesis}"


def azure(**more):
    return aloai_env.load({"ALO_ENV": "local", "CLOUD": "azure"} | more)


# ---- settings


def test_deployments_are_read_by_role():
    settings = azure(
        AZURE_OPENAI_DEPLOYMENTS=json.dumps(
            {"grader": "gpt-4.1", "quick": "gpt-4.1-mini"}
        )
    )
    assert deployment(settings, "grader") == "gpt-4.1"
    assert deployment(settings, "quick") == "gpt-4.1-mini"


def test_a_role_with_no_deployment_is_named():
    settings = azure(AZURE_OPENAI_DEPLOYMENTS='{"grader": "gpt-4.1"}')
    with pytest.raises(aloai_env.ConfigError, match="'embedding'"):
        deployment(settings, "embedding")
    with pytest.raises(aloai_env.ConfigError, match="'grader'"):
        deployment(azure(), "grader")


@pytest.mark.parametrize(
    "raw", ["not json", "[1]", '{"grader": 3}', '{"grader": ""}', '{"1": {}}']
)
def test_deployments_that_are_not_roles_to_names_are_refused(raw):
    with pytest.raises(aloai_env.ConfigError, match="AZURE_OPENAI_DEPLOYMENTS"):
        azure(AZURE_OPENAI_DEPLOYMENTS=raw)


def test_the_openai_base_url_is_the_v1_api_of_the_resource():
    settings = azure(AZURE_OPENAI_ENDPOINT="https://aloai.openai.azure.com/")
    assert openai_base_url(settings) == "https://aloai.openai.azure.com/openai/v1/"
    with pytest.raises(aloai_env.ConfigError, match="AZURE_OPENAI_ENDPOINT"):
        openai_base_url(azure())


def test_azure_ai_settings_are_read_from_the_environment():
    settings = azure(
        AZURE_OPENAI_ENDPOINT="https://aloai.openai.azure.com",
        AZURE_SPEECH_REGION="swedencentral",
        AZURE_SPEECH_RESOURCE_ID="/subscriptions/s/resourceGroups/r/providers/x/accounts/a",
        AZURE_SPEECH_LOCALE="en-NG",
    )
    assert settings.openai_endpoint == "https://aloai.openai.azure.com"
    assert (settings.speech_region, settings.speech_locale) == (
        "swedencentral",
        "en-NG",
    )
    assert settings.speech_resource_id.endswith("accounts/a")
    assert azure().speech_locale == "en-GB"
    assert azure().openai_deployments is None


@pytest.mark.parametrize("name", ["AZURE_OPENAI_API_KEY", "AZURE_SPEECH_KEY"])
def test_a_key_is_refused_when_hosted_but_allowed_locally(name):
    hosted = {
        "CLOUD": "azure",
        "AI_MODE": "live",
        "CONTAINER_APP_NAME": "aloai-core",
        name: "k",
    }
    with pytest.raises(aloai_env.ConfigError, match=name):
        aloai_env.load(hosted)
    local = azure(**{name: "k"})
    assert "k" in (local.openai_key, local.speech_key)


# ---- the audio Speech takes


def flac(samples, rate) -> bytes:
    buffer = io.BytesIO()
    soundfile.write(buffer, samples, rate, format="FLAC")
    return buffer.getvalue()


def test_16_khz_flac_becomes_16_bit_mono_pcm():
    tone = (0.1 * np.sin(np.linspace(0, 100, 16_000))).astype(np.float32)
    pcm = pcm16(flac(tone, 16_000))
    assert len(pcm) == 2 * 16_000
    assert np.allclose(np.frombuffer(pcm, dtype="<i2") / 32768, tone, atol=2e-3)


def test_two_channels_are_mixed_to_one():
    left = (0.2 * np.ones(1_600)).astype(np.float32)
    stereo = np.stack([left, 0 * left], axis=1)
    samples = np.frombuffer(pcm16(flac(stereo, 16_000)), dtype="<i2") / 32768
    assert samples.shape == (1_600,)
    assert np.allclose(samples, 0.1, atol=2e-3)


def test_audio_at_another_sample_rate_is_refused():
    with pytest.raises(ValueError, match="8000 Hz"):
        pcm16(flac(np.zeros(8_000, dtype=np.float32), 8_000))


# ---- what a recognition returns


def result(status="Success", words=None, **more):
    best = {
        "Confidence": 0.9,
        "Lexical": "x",
        "Words": words if words is not None else [],
    }
    return json.dumps({"RecognitionStatus": status, "NBest": [best]} | more)


def test_the_words_of_the_best_alternative_come_with_their_confidence():
    words = [
        {"Word": "ada", "Offset": 0, "Duration": 5, "Confidence": 0.93},
        {"Word": "ran", "Offset": 6, "Duration": 5, "Confidence": 0.41},
    ]
    assert words_from_result(result(words=words)) == [("ada", 0.93), ("ran", 0.41)]


def test_a_word_with_no_confidence_has_none():
    assert words_from_result(result(words=[{"Word": "ada", "Offset": 0}])) == [
        ("ada", None)
    ]


def test_an_empty_word_is_dropped():
    words = [{"Word": "", "Confidence": 0.9}, {"Confidence": 0.9}, {"Word": "ada"}]
    assert words_from_result(result(words=words)) == [("ada", None)]


@pytest.mark.parametrize(
    "raw",
    [
        result(status="NoMatch", words=[{"Word": "ada"}]),
        result(status="InitialSilenceTimeout"),
        json.dumps({"RecognitionStatus": "Success"}),
        json.dumps({"RecognitionStatus": "Success", "NBest": []}),
        json.dumps({"RecognitionStatus": "Success", "NBest": [{"Words": None}]}),
        json.dumps(
            {
                "RecognitionStatus": "Success",
                "NBest": [{"Words": [{"Confidence": 1}, 3]}],
            }
        ),
        "[]",
        "not json",
        "",
    ],
)
def test_a_recognition_that_gave_no_words_is_empty(raw):
    assert words_from_result(raw) == []


# ---- the speech a voice is asked to make


def parse(ssml: str) -> ET.Element:
    return ET.fromstring(ssml)


def test_plain_text_is_said_by_the_voice_in_its_locale():
    root = parse(
        build_ssml("That word is rain.", voice="en-NG-EzinneNeural", locale="en-NG")
    )
    assert root.attrib["{http://www.w3.org/XML/1998/namespace}lang"] == "en-NG"
    [voice] = root.findall(f"{SSML}voice")
    assert voice.attrib["name"] == "en-NG-EzinneNeural"
    assert voice.text == "That word is rain."


def test_a_speaking_rate_wraps_the_text_in_prosody():
    root = parse(build_ssml("Hello.", voice="v", locale="en-NG", rate="-10%"))
    [prosody] = root.iter(f"{SSML}prosody")
    assert (prosody.attrib["rate"], prosody.text) == ("-10%", "Hello.")


def test_a_name_is_spoken_from_its_ipa():
    ssml = build_ssml(
        "That word is Tunde.", voice="v", locale="en-NG", ipa=("Tunde", "ˈtundɛ")
    )
    [phoneme] = parse(ssml).iter(f"{SSML}phoneme")
    assert (phoneme.attrib["alphabet"], phoneme.attrib["ph"], phoneme.text) == (
        "ipa",
        "ˈtundɛ",
        "Tunde",
    )
    assert "".join(parse(ssml).find(f"{SSML}voice").itertext()) == "That word is Tunde."


def test_ipa_and_rate_together_nest_the_phoneme_inside_the_prosody():
    ssml = build_ssml(
        "Say Tunde.", voice="v", locale="en-NG", rate="-5%", ipa=("Tunde", "ˈtundɛ")
    )
    [prosody] = parse(ssml).iter(f"{SSML}prosody")
    assert prosody.find(f"{SSML}phoneme") is not None


def test_text_and_attributes_cannot_break_out_of_the_markup():
    ssml = build_ssml(
        'Tom & <b>"Jerry"</b>', voice='v"x', locale="en-NG", ipa=("Tom", 'a"b<c')
    )
    root = parse(ssml)  # still well-formed
    assert root.find(f"{SSML}voice").attrib["name"] == 'v"x'
    assert "".join(root.itertext()) == 'Tom & <b>"Jerry"</b>'
    assert list(root.iter(f"{SSML}phoneme"))[0].attrib["ph"] == 'a"b<c'


def test_an_ipa_word_that_is_not_in_the_text_is_refused():
    with pytest.raises(ValueError, match="'Tunde' is not in"):
        build_ssml(
            "That word is rain.", voice="v", locale="en-NG", ipa=("Tunde", "ˈtundɛ")
        )
