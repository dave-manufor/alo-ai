import jwt
import pytest
from services.account.auth import GuardianVerifier
from services.account.errors import AccountError
from services.account.tests.support import (
    AUDIENCE,
    GUARDIAN,
    KEY,
    OTHER_KEY,
    SETTINGS,
    TENANT,
    token,
)

VERIFIER = GuardianVerifier(SETTINGS, signing_key=lambda _token: KEY.public_key())


def test_a_valid_token_names_the_guardian_by_object_id_not_email():
    principal = VERIFIER.verify(token())
    assert principal.guardian_id == GUARDIAN
    assert principal.email == "guardian@example.com"
    assert principal.sign_in_method == "email_code"


def test_a_google_sign_in_is_read_from_the_identity_provider_claim():
    assert VERIFIER.verify(token(idp="google.com")).sign_in_method == "google"
    assert VERIFIER.verify(token(idp="Google")).sign_in_method == "google"
    assert VERIFIER.verify(token(idp="other.example")).sign_in_method == "email_code"


@pytest.mark.parametrize("email", [None, "", 7])
def test_a_token_without_a_usable_email_still_verifies_with_no_email(email):
    assert VERIFIER.verify(token(email=email)).email is None


def test_the_scope_may_be_one_of_several():
    assert VERIFIER.verify(token(scp="openid access_as_user profile")).guardian_id == GUARDIAN


@pytest.mark.parametrize(
    ("what", "changes"),
    [
        ("expired", {"exp": 1_000_000_000}),
        ("wrong audience", {"aud": "someone-else"}),
        ("wrong issuer", {"iss": "https://evil.example/v2.0"}),
        ("wrong tenant", {"tid": "00000000-0000-0000-0000-000000000000"}),
        ("missing tenant", {"tid": None}),
        ("missing scope", {"scp": None}),
        ("other scope", {"scp": "read_only"}),
        ("scope that only contains ours", {"scp": "not_access_as_user_at_all"}),
        ("missing object id", {"oid": None}),
        ("empty object id", {"oid": ""}),
        ("missing expiry", {"exp": None}),
        ("missing audience", {"aud": None}),
        ("missing issuer", {"iss": None}),
    ],
)
def test_a_token_that_is_not_for_this_service_is_refused(what, changes):
    with pytest.raises(AccountError) as error:
        VERIFIER.verify(token(**changes))
    assert (error.value.status, error.value.code) == (401, "UNAUTHENTICATED"), what


def test_a_token_signed_with_another_key_is_refused():
    with pytest.raises(AccountError) as error:
        VERIFIER.verify(token(OTHER_KEY))
    assert error.value.status == 401


def test_a_token_that_is_not_a_token_is_refused():
    with pytest.raises(AccountError) as error:
        VERIFIER.verify("not.a.token")
    assert error.value.status == 401


def test_a_token_with_no_signature_is_refused_whatever_it_claims():
    unsigned = jwt.encode(
        {"iss": SETTINGS.issuer, "aud": AUDIENCE, "tid": TENANT, "oid": GUARDIAN,
         "scp": "access_as_user", "exp": 4_000_000_000},
        key=None,
        algorithm="none",
    )
    with pytest.raises(AccountError) as error:
        VERIFIER.verify(unsigned)
    assert error.value.status == 401


def test_a_token_signed_with_a_shared_secret_is_refused():
    forged = jwt.encode(
        {"iss": SETTINGS.issuer, "aud": AUDIENCE, "tid": TENANT, "oid": GUARDIAN,
         "scp": "access_as_user", "exp": 4_000_000_000},
        "secret" * 8,
        algorithm="HS256",
    )
    with pytest.raises(AccountError):
        VERIFIER.verify(forged)


def test_keys_that_cannot_be_fetched_are_a_retryable_503_not_a_sign_out():
    def unreachable(_token):
        raise jwt.PyJWKClientConnectionError("no route to Entra")

    verifier = GuardianVerifier(SETTINGS, signing_key=unreachable)
    with pytest.raises(AccountError) as error:
        verifier.verify(token())
    assert (error.value.status, error.value.code, error.value.retryable) == (
        503,
        "AUTH_UNAVAILABLE",
        True,
    )


def test_a_key_id_the_tenant_does_not_publish_is_refused():
    def unknown_key(_token):
        raise jwt.PyJWKClientError("unable to find a signing key that matches")

    verifier = GuardianVerifier(SETTINGS, signing_key=unknown_key)
    with pytest.raises(AccountError) as error:
        verifier.verify(token())
    assert error.value.status == 401
