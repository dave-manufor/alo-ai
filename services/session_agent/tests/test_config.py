import pytest
from services.session_agent import config
from services.session_agent.main import main


def test_defaults():
    assert config.load({}) == config.Config(
        alo_env="", ai_mode="fixtures", voice_mode="cache_first", session_profile="standard"
    )


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


def test_main_reports_that_the_worker_is_not_wired_yet(capsys):
    assert main(["dev"], {}) == 3
    assert "not wired" in capsys.readouterr().err


def test_main_reads_the_process_environment_by_default(monkeypatch):
    monkeypatch.setenv("SESSION_PROFILE", "fast")
    assert main(["dev"]) == 1
