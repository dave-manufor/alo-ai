"""The Core service's settings guard and app factory."""

import aloai_env
import pytest
from fastapi.testclient import TestClient
from services.core.main import create_app
from services.core.tests.support import quick_request


def test_the_app_refuses_to_start_with_local_shortcuts_on_cloud_run():
    with pytest.raises(aloai_env.ConfigError):
        create_app({"ALO_ENV": "local", "K_SERVICE": "aloai-core"})


def test_the_local_app_serves_the_quick_endpoint(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    monkeypatch.setenv("PUBSUB_EMULATOR_HOST", "localhost:8085")
    http = TestClient(create_app({"ALO_ENV": "local", "AI_MODE": "fixtures"}))
    response = http.post("/v1/grade:quick", json=quick_request("READING", 0, ""))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_the_local_app_serves_the_generate_endpoint(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    monkeypatch.setenv("PUBSUB_EMULATOR_HOST", "localhost:8085")
    http = TestClient(create_app({"ALO_ENV": "local", "AI_MODE": "fixtures"}))
    response = http.post("/v1/passages:generate", json={"tags": ["cars"]})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize(
    "env",
    [
        {"ALO_ENV": "local", "COACH_ON": "yes"},
        {"ALO_ENV": "", "AI_MODE": "fixtures"},
    ],
    ids=["unclear coach flag", "no account url off local"],
)
def test_the_app_refuses_to_start_with_coach_settings_missing_or_unclear(monkeypatch, env):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    monkeypatch.setenv("PUBSUB_EMULATOR_HOST", "localhost:8085")
    with pytest.raises(aloai_env.ConfigError):
        create_app(env)
