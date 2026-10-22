import pytest
from aloai_env import ConfigError
from services.account.settings import AccountSettings
from services.account.tests.support import AUDIENCE, TENANT

ENV = {
    "ENTRA_TENANT_ID": TENANT,
    "ENTRA_AUTHORITY": "https://aloai.ciamlogin.com/",
    "ENTRA_API_AUDIENCE": AUDIENCE,
}


def test_the_issuer_keys_and_scope_follow_from_the_tenant():
    settings = AccountSettings.from_env(ENV, hosted=False)
    assert settings.authority == "https://aloai.ciamlogin.com"
    assert settings.issuer == f"https://{TENANT}.ciamlogin.com/{TENANT}/v2.0"
    assert settings.jwks_url == f"https://aloai.ciamlogin.com/{TENANT}/discovery/v2.0/keys"
    assert settings.scope == "access_as_user"
    assert settings.web_origin is None


def test_the_issuer_scope_and_origin_can_be_set():
    settings = AccountSettings.from_env(
        ENV
        | {
            "ENTRA_ISSUER": "https://login.example/v2.0",
            "ENTRA_API_SCOPE": "other",
            "WEB_ORIGIN": "https://web.example.test/",
        },
        hosted=True,
    )
    assert (settings.issuer, settings.scope) == ("https://login.example/v2.0", "other")
    assert settings.web_origin == "https://web.example.test"


@pytest.mark.parametrize("name", ["ENTRA_TENANT_ID", "ENTRA_AUTHORITY", "ENTRA_API_AUDIENCE"])
def test_a_missing_entra_setting_is_named(name):
    env = {key: value for key, value in ENV.items() if key != name}
    with pytest.raises(ConfigError, match=name):
        AccountSettings.from_env(env, hosted=False)


def test_a_hosted_service_must_name_the_one_web_origin():
    with pytest.raises(ConfigError, match="WEB_ORIGIN"):
        AccountSettings.from_env(ENV, hosted=True)


def test_livekit_settings_are_read_and_empty_means_unset():
    settings = AccountSettings.from_env(
        ENV | {"LIVEKIT_URL": "wss://x.test", "LIVEKIT_API_KEY": "k", "LIVEKIT_API_SECRET": ""},
        hosted=False,
    )
    assert (settings.livekit_url, settings.livekit_api_key) == ("wss://x.test", "k")
    assert settings.livekit_api_secret is None
