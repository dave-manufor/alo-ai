"""The Session Agent on Azure (CLOUD=azure): the storage it writes through, the URIs it
names, the hosted-service guard, the speech it listens with and the clips it makes. Fake
clients only: nothing here reaches Azure."""

import uuid
import xml.etree.ElementTree as ET

import aloai_env
import pytest
from aloai_blobs import MemoryBlobs
from services.session_agent import config, livekit_worker
from services.session_agent.cloud import BlobBucket
from services.session_agent.clips.azure import word_synthesizer
from services.session_agent.clips.seed import WordToSeed, seed_words
from services.session_agent.clips.store import ClipStore, MemoryBucket
from services.session_agent.recorder import object_name
from services.session_agent.recording import AudioLog

SSML = "{http://www.w3.org/2001/10/synthesis}"
SESSION_UUID = "3f2b9c1e-7d44-4c0b-8a52-0e6f1d9a7b10"


def shared(**more) -> aloai_env.Config:
    return aloai_env.load({"ALO_ENV": "local", "CLOUD": "azure"} | more, receives_pushes=False)


# ---- storage


@pytest.mark.parametrize(
    "cloud, uri",
    [("gcp", "gs://aloai-audio/s/a.flac"), ("azure", "az://audio/s/a.flac")],
)
def test_a_bucket_writes_through_the_blobs_of_its_cloud(cloud, uri):
    blobs = MemoryBlobs()
    bucket = BlobBucket(blobs, cloud, uri.split("/")[2])
    assert bucket.exists("s/a.flac") is False
    bucket.upload("s/a.flac", b"one", "audio/flac")
    assert (blobs.read(uri), bucket.exists("s/a.flac")) == (b"one", True)
    assert blobs.content_types[uri] == "audio/flac"
    bucket.upload("s/a.flac", b"two", "audio/flac")
    assert blobs.read(uri) == b"two"


def test_a_clip_is_written_only_if_it_is_not_there():
    blobs = MemoryBlobs()
    bucket = BlobBucket(blobs, "azure", "clips")
    assert bucket.upload_if_absent("vp/v1/words/rain.mp3", b"first", "audio/mpeg") is True
    assert bucket.upload_if_absent("vp/v1/words/rain.mp3", b"second", "audio/mpeg") is False
    assert blobs.read("az://clips/vp/v1/words/rain.mp3") == b"first"


def test_the_clip_store_works_over_a_bucket_of_either_cloud():
    store = ClipStore(
        BlobBucket(MemoryBlobs(), "azure", "clips"), "clips", "vp_azure_v1", "v1", "az"
    )
    assert store.has_word("rain") is False
    assert store.put_word("rain", b"mp3") is True
    assert store.has_word("rain") is True
    assert store.uri(store.word_clip_name("rain")) == "az://clips/vp_azure_v1/v1/words/rain.mp3"


def test_the_clip_store_names_gs_uris_unless_told_otherwise():
    store = ClipStore(MemoryBucket(), "aloai-dev-clips", "vp_google_v1", "v1")
    assert store.uri("x.mp3") == "gs://aloai-dev-clips/x.mp3"


# ---- the URIs in events and documents


def test_a_turns_audio_is_named_in_the_scheme_of_the_cloud():
    azure = AudioLog("audio", SESSION_UUID, scheme="az").new_turn("READING")
    google = AudioLog("aloai-audio", SESSION_UUID).new_turn("READING")
    assert azure.audio_uri.startswith(f"az://audio/{SESSION_UUID}/READING/")
    assert google.audio_uri.startswith(f"gs://aloai-audio/{SESSION_UUID}/READING/")
    assert azure.audio_uri.endswith(".flac")
    assert uuid.UUID(azure.audio_uri.rsplit("/", 1)[1].removesuffix(".flac")).version == 4


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("gs://aloai-audio/s/READING/a.flac", ("aloai-audio", "s/READING/a.flac")),
        ("az://audio/s/READING/a.flac", ("audio", "s/READING/a.flac")),
    ],
)
def test_an_audio_uri_splits_into_its_container_and_object_name(uri, expected):
    assert object_name(uri) == expected


# ---- settings and the hosted guard


@pytest.mark.parametrize("name", ["CONTAINER_APP_NAME", "CONTAINER_APP_JOB_NAME"])
def test_local_shortcuts_are_refused_on_container_apps(name):
    with pytest.raises(config.ConfigError, match="Container Apps"):
        config.load({"ALO_ENV": "local", name: "aloai-session-agent"})


def test_local_shortcuts_are_still_refused_on_cloud_run():
    with pytest.raises(config.ConfigError, match="Cloud Run"):
        config.load({"ALO_ENV": "local", "K_SERVICE": "aloai-session-agent"})
    assert config.load({"ALO_ENV": "local"}).alo_env == "local"


def test_the_worker_settings_default_to_gcp_and_the_google_clips_url():
    settings = config.worker_settings({})
    assert settings.cloud == "gcp"
    assert settings.clips_base_url == "https://storage.googleapis.com/aloai-dev-clips"
    assert settings.core_audience == ""


def test_on_azure_clips_are_fetched_from_the_public_container_of_the_storage_account():
    settings = config.worker_settings(
        {"CLOUD": "azure", "CLIPS_BUCKET": "clips", "AZURE_STORAGE_ACCOUNT": "aloaistore"}
    )
    assert settings.cloud == "azure"
    assert settings.clips_base_url == "https://aloaistore.blob.core.windows.net/clips"


def test_the_clips_url_can_be_overridden_for_a_cdn():
    env = {"CLOUD": "azure", "CLIPS_BASE_URL": "https://cdn.aloai.example/clips"}
    assert config.worker_settings(env).clips_base_url == "https://cdn.aloai.example/clips"


def test_on_azure_the_clips_url_must_come_from_somewhere():
    with pytest.raises(config.ConfigError, match="CLIPS_BASE_URL or AZURE_STORAGE_ACCOUNT"):
        config.worker_settings({"CLOUD": "azure"})


def test_an_unknown_cloud_is_refused():
    with pytest.raises(config.ConfigError, match="CLOUD"):
        config.worker_settings({"CLOUD": "aws"})


def test_the_audience_of_the_token_for_core_is_its_own_setting():
    env = {"CORE_URL": "http://core.internal", "CORE_AUDIENCE": "api://aloai-core"}
    assert config.worker_settings(env).core_audience == "api://aloai-core"


def test_a_session_agent_on_cloud_run_needs_no_push_identity():
    settings = aloai_env.load(
        {"K_SERVICE": "aloai-session-agent", "AI_MODE": "live"}, receives_pushes=False
    )
    assert (settings.hosted, settings.push_service_account) == (True, None)
    with pytest.raises(aloai_env.ConfigError, match="PUSH_SERVICE_ACCOUNT"):
        aloai_env.load({"K_SERVICE": "aloai-core", "AI_MODE": "live"})


# ---- the token for Core


def test_there_is_no_token_for_core_when_not_hosted():
    assert livekit_worker._id_token(config.worker_settings({}), shared()) is None


def test_the_token_for_core_is_for_its_audience_and_fresh_each_time(monkeypatch):
    asked = []
    monkeypatch.setattr(
        livekit_worker,
        "service_token",
        lambda config_, audience: asked.append((config_.cloud, audience)) or f"t{len(asked)}",
    )
    hosted = aloai_env.load(
        {"CLOUD": "azure", "AI_MODE": "live", "CONTAINER_APP_NAME": "aloai-session-agent"},
        receives_pushes=False,
    )
    settings = config.worker_settings(
        {
            "CORE_URL": "http://core.internal",
            "CORE_AUDIENCE": "api://aloai-core",
            "CLOUD": "azure",
            "CLIPS_BASE_URL": "x",
        }
    )
    token = livekit_worker._id_token(settings, hosted)
    assert (token(), token()) == ("t1", "t2")
    assert asked == [("azure", "api://aloai-core")] * 2


def test_on_azure_without_an_audience_core_is_called_without_a_token(monkeypatch, caplog):
    monkeypatch.setattr(
        livekit_worker, "service_token", lambda *args: pytest.fail("a token was asked for")
    )
    hosted = aloai_env.load(
        {"CLOUD": "azure", "AI_MODE": "live", "CONTAINER_APP_NAME": "aloai-session-agent"},
        receives_pushes=False,
    )
    settings = config.worker_settings({"CLOUD": "azure", "CLIPS_BASE_URL": "x"})
    assert livekit_worker._id_token(settings, hosted) is None
    assert "CORE_AUDIENCE is not set" in caplog.text


def test_the_token_for_core_defaults_to_its_url_as_the_audience(monkeypatch):
    asked = []
    monkeypatch.setattr(
        livekit_worker, "service_token", lambda config_, audience: asked.append(audience) or "t"
    )
    hosted = aloai_env.load(
        {"K_SERVICE": "aloai-session-agent", "AI_MODE": "live"}, receives_pushes=False
    )
    livekit_worker._id_token(config.worker_settings({"CORE_URL": "https://core.run.app"}), hosted)()
    assert asked == ["https://core.run.app"]


# ---- listening


def test_azure_speech_is_reached_with_a_key_locally():
    options = livekit_worker.azure_stt_options(
        shared(
            AZURE_SPEECH_REGION="swedencentral", AZURE_SPEECH_KEY="k", AZURE_SPEECH_LOCALE="en-NG"
        )
    )
    assert options == {"language": "en-NG", "speech_region": "swedencentral", "speech_key": "k"}


def test_azure_speech_is_reached_with_the_identitys_token_when_hosted(monkeypatch):
    monkeypatch.setattr("aloai_azure.entra_token", lambda: "tok")
    options = livekit_worker.azure_stt_options(
        shared(AZURE_SPEECH_REGION="swedencentral", AZURE_SPEECH_RESOURCE_ID="/subscriptions/s/a")
    )
    assert options == {
        "language": "en-GB",
        "speech_region": "swedencentral",
        "speech_auth_token": "aad#/subscriptions/s/a#tok",
    }


def test_there_is_no_speech_to_text_with_recorded_responses():
    cfg = config.load({"ALO_ENV": "local", "AI_MODE": "fixtures"})
    assert livekit_worker._stt(cfg, shared()) is None


def test_live_azure_listens_with_azure_speech(monkeypatch):
    built = []

    class FakeSTT:
        def __init__(self, **options):
            built.append(options)

        def stream(self):
            return "stream"

    monkeypatch.setattr("livekit.plugins.azure.STT", FakeSTT)
    cfg = config.load({"ALO_ENV": "local", "AI_MODE": "live"})
    speech = livekit_worker._stt(
        cfg, shared(AI_MODE="live", AZURE_SPEECH_REGION="swedencentral", AZURE_SPEECH_KEY="k")
    )
    assert speech == "stream"
    assert built == [{"language": "en-GB", "speech_region": "swedencentral", "speech_key": "k"}]


# ---- clips


def test_the_word_clip_is_the_sentence_said_by_the_azure_voice():
    asked = []
    make = word_synthesizer(
        lambda ssml: asked.append(ssml) or b"mp3", voice="en-NG-EzinneNeural", locale="en-NG"
    )
    assert make("rain", None) == b"mp3"
    [ssml] = asked
    voice = ET.fromstring(ssml).find(f"{SSML}voice")
    assert voice.attrib["name"] == "en-NG-EzinneNeural"
    assert voice.text == "That word is rain."


def test_a_name_in_a_word_clip_is_spoken_from_its_ipa():
    asked = []
    make = word_synthesizer(lambda ssml: asked.append(ssml) or b"mp3", voice="v", locale="en-NG")
    make("Tunde", "ˈtundɛ")
    [phoneme] = ET.fromstring(asked[0]).iter(f"{SSML}phoneme")
    assert (phoneme.attrib["ph"], phoneme.text) == ("ˈtundɛ", "Tunde")


def test_the_clip_store_is_filled_with_azure_clips():
    blobs = MemoryBlobs()
    store = ClipStore(BlobBucket(blobs, "azure", "clips"), "clips", "vp_azure_v1", "v1", "az")
    make = word_synthesizer(lambda ssml: b"mp3", voice="v", locale="en-NG")
    report = seed_words([WordToSeed("rain"), WordToSeed("Tunde", "ˈtundɛ")], store, make)
    assert len(report.written) == 2
    assert report.failed == {}
    assert all(uri.startswith("az://clips/vp_azure_v1/v1/words/") for uri in blobs.blobs)
    again = seed_words([WordToSeed("rain")], store, make)
    assert again.written == [] and len(again.existing) == 1
