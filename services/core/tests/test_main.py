"""The Core service's settings guard and app factory."""

import pytest
from fastapi.testclient import TestClient
from services.core import config
from services.core.main import create_app
from services.core.tests.support import quick_request


def test_local_shortcuts_are_refused_on_cloud_run():
    with pytest.raises(config.ConfigError):
        config.load({"ALO_ENV": "local", "K_SERVICE": "aloai-core"})


def test_an_unknown_ai_mode_is_refused():
    with pytest.raises(config.ConfigError):
        config.load({"AI_MODE": "mock"})


def test_settings_default_to_recorded_ai_in_the_eu_project():
    settings = config.load({})
    assert (settings.ai_mode, settings.project, settings.location) == (
        "fixtures",
        "aloai-dev",
        "europe-west1",
    )


def test_the_app_refuses_to_start_with_local_shortcuts_on_cloud_run():
    with pytest.raises(config.ConfigError):
        create_app({"ALO_ENV": "local", "K_SERVICE": "aloai-core"})


def test_the_local_app_serves_the_quick_endpoint(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    monkeypatch.setenv("PUBSUB_EMULATOR_HOST", "localhost:8085")
    http = TestClient(create_app({"ALO_ENV": "local", "AI_MODE": "fixtures"}))
    response = http.post("/v1/grade:quick", json=quick_request("READING", 0, ""))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
