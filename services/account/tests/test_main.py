import pytest
from aloai_env import ConfigError
from aloai_store import MemoryStore
from fastapi.testclient import TestClient
from services.account.auth import GuardianVerifier
from services.account.main import build_app, create_app
from services.account.settings import AccountSettings
from services.account.tests.support import (
    AUDIENCE,
    GUARDIAN,
    KEY,
    SETTINGS,
    TENANT,
    bearer,
)


def client(settings: AccountSettings = SETTINGS) -> TestClient:
    verifier = GuardianVerifier(settings, signing_key=lambda _token: KEY.public_key())
    return TestClient(build_app(settings, MemoryStore(), verifier))


def test_health_needs_no_sign_in():
    response = client().get("/healthz")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_me_is_the_verified_guardian():
    response = client().get("/v1/me", headers=bearer())
    assert response.status_code == 200
    assert response.json() == {
        "guardian_id": GUARDIAN,
        "email": "guardian@example.com",
        "sign_in_method": "email_code",
    }


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
        {"Authorization": "Basic Z3VhcmRpYW46cHc="},
        {"Authorization": "Bearer not.a.token"},
        {"Authorization": "guardian_demo_001"},
    ],
)
def test_me_refuses_a_call_without_a_good_bearer_token(headers):
    response = client().get("/v1/me", headers=headers)
    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "UNAUTHENTICATED", "message": "Please sign in again.", "retryable": False}
    }


def test_me_refuses_an_expired_token_in_the_error_shape_of_the_other_services():
    response = client().get("/v1/me", headers=bearer(exp=1_000_000_000))
    assert response.status_code == 401
    assert set(response.json()["error"]) == {"code", "message", "retryable"}


def test_the_scheme_name_is_case_insensitive():
    token = bearer()["Authorization"].split(" ", 1)[1]
    response = client().get("/v1/me", headers={"Authorization": f"bearer {token}"})
    assert response.status_code == 200


def test_the_web_origin_may_call_and_no_other_origin_is_allowed():
    allowed = client().options(
        "/v1/me",
        headers={
            "Origin": "https://web.example.test",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "https://web.example.test"
    other = client().options(
        "/v1/me",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in other.headers


def test_without_a_web_origin_no_cors_headers_are_added():
    settings = AccountSettings(**{**SETTINGS.__dict__, "web_origin": None})
    response = client(settings).get("/healthz", headers={"Origin": "https://web.example.test"})
    assert "access-control-allow-origin" not in response.headers


def _env(**more):
    return {
        "ENTRA_TENANT_ID": TENANT,
        "ENTRA_AUTHORITY": "https://aloai.ciamlogin.com/",
        "ENTRA_API_AUDIENCE": AUDIENCE,
        "ALO_ENV": "local",
        **more,
    }


def test_create_app_builds_from_the_environment(monkeypatch):
    # The real store needs cloud credentials, so the test hands it an in-memory one.
    monkeypatch.setattr("services.account.main.open_store", lambda config: MemoryStore())
    app = create_app(_env())
    assert TestClient(app).get("/healthz").status_code == 200


def test_create_app_refuses_local_shortcuts_when_hosted():
    with pytest.raises(ConfigError, match="ALO_ENV=local"):
        create_app(_env(CONTAINER_APP_NAME="aloai-account", WEB_ORIGIN="https://web.example.test"))


def test_create_app_refuses_a_hosted_start_without_a_web_origin():
    env = _env(CONTAINER_APP_NAME="aloai-account", AI_MODE="live")
    env.pop("ALO_ENV")
    with pytest.raises(ConfigError, match="WEB_ORIGIN"):
        create_app(env)
