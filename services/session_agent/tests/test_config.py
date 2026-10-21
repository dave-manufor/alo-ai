import pytest
from services.session_agent import config
from services.session_agent.main import main


def test_defaults():
    assert config.load({}) == config.Config(
        alo_env="",
        ai_mode="fixtures",
        voice_mode="cache_first",
        session_profile="standard",
        generator_on=False,  # off until the generator's evaluation sets pass
    )


@pytest.mark.parametrize(("value", "on"), [("true", True), ("false", False)])
def test_the_generator_switch_is_a_strict_flag(value, on):
    assert config.load({"GENERATOR_ON": value}).generator_on is on


def test_an_unclear_generator_switch_is_refused():
    with pytest.raises(config.ConfigError, match="GENERATOR_ON"):
        config.load({"GENERATOR_ON": "yes"})


def test_values_come_from_the_environment():
    loaded = config.load(
        {"ALO_ENV": "prod", "AI_MODE": "live", "VOICE_MODE": "live_first", "SESSION_PROFILE": "demo"}
    )
    assert (loaded.ai_mode, loaded.voice_mode, loaded.session_profile) == (
        "live",
        "live_first",
        "demo",
    )


@pytest.mark.parametrize(
    "env",
    [{"AI_MODE": "mock"}, {"VOICE_MODE": "browser"}, {"SESSION_PROFILE": "fast"}],
)
def test_unknown_values_are_refused(env):
    with pytest.raises(config.ConfigError):
        config.load(env)


def test_local_shortcuts_are_refused_on_cloud_run():
    with pytest.raises(config.ConfigError, match="Cloud Run"):
        config.load({"ALO_ENV": "local", "K_SERVICE": "aloai-session-agent"})


def test_local_is_fine_without_k_service_and_cloud_run_without_local():
    assert config.load({"ALO_ENV": "local"}).alo_env == "local"
    assert config.load({"K_SERVICE": "aloai-session-agent"}).alo_env == ""


def test_main_refuses_to_start_on_cloud_run_with_local_shortcuts(capsys):
    code = main(["start"], {"ALO_ENV": "local", "K_SERVICE": "x"})
    assert code == 1 and "refusing to start" in capsys.readouterr().err


def test_main_needs_a_mode(capsys):
    assert main([], {}) == 2
    assert main(["other"], {}) == 2
    assert "usage" in capsys.readouterr().err


@pytest.mark.parametrize("mode", ["dev", "start", "console"])
def test_main_hands_good_settings_to_the_worker(mode):
    ran = []
    assert main([mode], {}, run=ran.append) == 0
    assert ran == [[mode]]


def test_main_does_not_start_the_worker_with_bad_settings():
    ran = []
    assert main(["start"], {"ALO_ENV": "local", "K_SERVICE": "x"}, run=ran.append) == 1
    assert ran == []


def test_worker_settings_default_to_the_dev_project_and_can_be_overridden():
    defaults = config.worker_settings({})
    assert (defaults.audio_bucket, defaults.clips_bucket) == ("aloai-dev-audio", "aloai-dev-clips")
    assert defaults.clips_base_url == "https://storage.googleapis.com/aloai-dev-clips"
    assert (defaults.stt_language, defaults.stt_location) == ("en-GB", "eu")
    assert defaults.bank_passage_id == ""  # the session profile's default bank passage
    assert defaults.vertex_location == "europe-west1"
    local = config.worker_settings(
        {"CLIPS_BUCKET": "c", "CLIPS_BASE_URL": "http://localhost:4443/c", "BANK_DIR": "x"}
    )
    assert (local.clips_base_url, local.bank_dir) == ("http://localhost:4443/c", "x")


def test_main_reads_the_process_environment_by_default(monkeypatch):
    monkeypatch.setenv("SESSION_PROFILE", "fast")
    assert main(["dev"]) == 1
