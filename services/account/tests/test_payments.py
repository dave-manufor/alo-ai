"""The parent subscription in Paystack test mode (PRD 11.1): checkout, confirm, the webhook and
the plan's paywall, against a fake Paystack (no network)."""

import dataclasses
import hashlib
import hmac
import io
import json
import logging
import urllib.error
from pathlib import Path

import pytest
from aloai_contracts import CHECKOUT_START, SUBSCRIPTION, SUBSCRIPTION_STATUS
from aloai_env import ConfigError
from aloai_store import MemoryStore
from services.account.paystack import PaystackApi, PaystackError, signature_ok
from services.account.settings import AccountSettings
from services.account.tests.support import GUARDIAN, NOW, SETTINGS, bearer, make_client

SECRET = "sk_test_fictional0000000000000000000000"
PLAN = "PLN_demo0000000001"
PAID = dataclasses.replace(SETTINGS, paystack_secret_key=SECRET, paystack_plan_code=PLAN)
OTHER = "guardian_other_002"
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures/contracts"


class FakePaystack:
    """Answers like Paystack's test mode; `paid` decides what Verify Transaction says."""

    def __init__(self, paid: dict | None = None, fail: bool = False) -> None:
        self.started: list[dict] = []
        self.verified: list[str] = []
        self.paid = paid
        self.fail = fail

    def initialize(self, **request) -> dict:
        if self.fail:
            raise PaystackError("HTTP 500")
        self.started.append(request)
        code = f"code_{request['reference']}"
        return {
            "authorization_url": f"https://checkout.paystack.com/{code}",
            "access_code": code,
            "reference": request["reference"],
        }

    def verify(self, reference: str) -> dict:
        self.verified.append(reference)
        if self.fail:
            raise PaystackError("URLError")
        return {"reference": reference, **(self.paid or {"status": "abandoned"})}


def paid(**changes) -> dict:
    """What Verify Transaction says for a paid plan transaction."""
    return {
        "status": "success",
        "currency": "NGN",
        "amount": 150000,
        "paid_at": "2026-01-15T09:00:00.000Z",
        "plan": PLAN,
        "customer": {"customer_code": "CUS_fictional001", "email": "guardian@example.com"},
    } | changes


def started(paystack: FakePaystack, settings: AccountSettings = PAID, store=None):
    client, store = make_client(settings=settings, store=store, paystack=paystack)
    response = client.post("/v1/checkout", headers=bearer())
    return client, store, response


def signed(event: dict, secret: str = SECRET) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
    return body, {"x-paystack-signature": signature, "Content-Type": "application/json"}


def test_the_fixtures_are_the_contract():
    SUBSCRIPTION.validate(json.loads((FIXTURES / "payments.subscription.json").read_text()))
    CHECKOUT_START.validate(json.loads((FIXTURES / "payments.checkout_start.json").read_text()))
    status = json.loads((FIXTURES / "payments.subscription_status.json").read_text())
    SUBSCRIPTION_STATUS.validate(status)


# ---- checkout


def test_checkout_records_the_guardian_then_starts_a_plan_transaction():
    paystack = FakePaystack()
    _client, store, response = started(paystack)
    assert response.status_code == 201
    reply = response.json()
    CHECKOUT_START.validate(reply)
    reference = reply["reference"]
    assert store.get(f"checkouts/{reference}")["guardian_id"] == GUARDIAN
    [request] = paystack.started
    # The plan is set here, never by the browser, and Paystack gets no child data.
    assert request == {
        "email": "guardian@example.com",
        "plan": PLAN,
        "amount_kobo": 150000,
        "reference": reference,
        "metadata": {"guardian_id": GUARDIAN},
    }
    assert [doc["action"] for p, doc in store.docs.items() if p.startswith("audit_log/")] == [
        "checkout.start"
    ]


def test_checkout_without_paystack_is_503():
    _client, _store, response = started(FakePaystack(), settings=SETTINGS)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PAYMENTS_UNAVAILABLE"
    _client, _store, response = started(None)
    assert response.status_code == 503


def test_checkout_when_paystack_fails_is_a_retryable_503_that_logs_no_secret(caplog):
    with caplog.at_level(logging.ERROR):
        _client, _store, response = started(FakePaystack(fail=True))
    assert response.status_code == 503 and response.json()["error"]["retryable"] is True
    assert SECRET not in caplog.text and "guardian@example.com" not in caplog.text


def test_a_subscribed_guardian_is_not_charged_again():
    paystack = FakePaystack(paid=paid())
    client, store, response = started(paystack)
    client.post(f"/v1/checkout/{response.json()['reference']}/confirm", headers=bearer())
    again = client.post("/v1/checkout", headers=bearer())
    assert again.status_code == 409
    assert len(paystack.started) == 1


# ---- confirm (after the popup) and the entitlement


def test_confirm_grants_only_what_paystack_says_is_paid():
    paystack = FakePaystack(paid=paid())
    client, store, response = started(paystack)
    reference = response.json()["reference"]
    assert client.get("/v1/subscription", headers=bearer()).json()["active"] is False
    confirmed = client.post(f"/v1/checkout/{reference}/confirm", headers=bearer())
    assert confirmed.status_code == 200
    SUBSCRIPTION_STATUS.validate(confirmed.json())
    assert confirmed.json() == {
        "schema_version": 1,
        "active": True,
        "plans_need_subscription": False,
        "current_period_end": "2026-02-15T09:00:00Z",
    }
    assert paystack.verified == [reference]
    subscription = store.get(f"subscriptions/{GUARDIAN}")
    SUBSCRIPTION.validate(subscription)
    assert (subscription["status"], subscription["customer_code"]) == ("active", "CUS_fictional001")
    assert store.get(f"checkouts/{reference}")["status"] == "PAID"


@pytest.mark.parametrize(
    "verified",
    [
        {"status": "abandoned"},
        paid(status="failed"),
        paid(currency="USD"),
        paid(plan="PLN_someotherplan1"),
        paid(plan=None),
    ],
)
def test_confirm_grants_nothing_paystack_does_not_say_is_this_plan_paid(verified):
    client, store, response = started(FakePaystack(paid=verified))
    confirmed = client.post(
        f"/v1/checkout/{response.json()['reference']}/confirm", headers=bearer()
    )
    assert confirmed.json()["active"] is False
    assert store.get(f"subscriptions/{GUARDIAN}") is None


def test_a_plan_given_as_an_object_is_read_too():
    client, _store, response = started(FakePaystack(paid=paid(plan={"plan_code": PLAN})))
    confirmed = client.post(
        f"/v1/checkout/{response.json()['reference']}/confirm", headers=bearer()
    )
    assert confirmed.json()["active"] is True
    client, _store, response = started(
        FakePaystack(paid=paid(plan=None, plan_object={"plan_code": PLAN}))
    )
    confirmed = client.post(
        f"/v1/checkout/{response.json()['reference']}/confirm", headers=bearer()
    )
    assert confirmed.json()["active"] is True


def test_another_guardians_or_an_unknown_checkout_is_a_404():
    client, _store, response = started(FakePaystack(paid=paid()))
    reference = response.json()["reference"]
    assert (
        client.post(f"/v1/checkout/{reference}/confirm", headers=bearer(oid=OTHER)).status_code
        == 404
    )
    assert client.post("/v1/checkout/pay_nope/confirm", headers=bearer()).status_code == 404
    assert client.post("/v1/checkout/bad%20id/confirm", headers=bearer()).status_code == 404


def test_confirm_when_paystack_is_down_is_a_retryable_503():
    paystack = FakePaystack(paid=paid())
    client, _store, response = started(paystack)
    paystack.fail = True
    confirmed = client.post(
        f"/v1/checkout/{response.json()['reference']}/confirm", headers=bearer()
    )
    assert confirmed.status_code == 503 and confirmed.json()["error"]["retryable"] is True


def test_a_subscription_runs_out_at_the_end_of_its_period():
    store = MemoryStore()
    subscription = json.loads((FIXTURES / "payments.subscription.json").read_text())
    store.set(
        f"subscriptions/{GUARDIAN}", subscription | {"current_period_end": "2026-01-01T00:00:00Z"}
    )
    client, _store = make_client(settings=PAID, store=store, paystack=FakePaystack())
    assert client.get("/v1/subscription", headers=bearer()).json()["active"] is False
    store.merge(f"subscriptions/{GUARDIAN}", {"current_period_end": "2026-03-01T00:00:00Z"})
    assert client.get("/v1/subscription", headers=bearer()).json()["active"] is True
    store.merge(f"subscriptions/{GUARDIAN}", {"status": "inactive"})
    assert client.get("/v1/subscription", headers=bearer()).json()["active"] is False


def test_the_subscription_status_needs_a_sign_in():
    client, _store = make_client(settings=PAID, paystack=FakePaystack())
    assert client.get("/v1/subscription").status_code == 401


# ---- the webhook


def charge_success(reference: str) -> dict:
    return {"event": "charge.success", "data": {"reference": reference, "status": "success"}}


def test_a_forged_or_missing_signature_is_refused_and_changes_nothing():
    paystack = FakePaystack(paid=paid())
    client, store, response = started(paystack)
    body, headers = signed(charge_success(response.json()["reference"]), secret="sk_test_wrong")
    assert client.post("/webhooks/paystack", content=body, headers=headers).status_code == 401
    del headers["x-paystack-signature"]
    assert client.post("/webhooks/paystack", content=body, headers=headers).status_code == 401
    assert paystack.verified == []
    assert store.get(f"subscriptions/{GUARDIAN}") is None


def test_a_webhook_without_payments_configured_is_refused():
    client, _store = make_client(settings=SETTINGS)
    body, headers = signed(charge_success("pay_1"))
    assert client.post("/webhooks/paystack", content=body, headers=headers).status_code == 401


def test_charge_success_is_verified_before_access_is_granted_and_handled_once():
    paystack = FakePaystack(paid=paid())
    client, store, response = started(paystack)
    reference = response.json()["reference"]
    body, headers = signed(charge_success(reference))
    first = client.post("/webhooks/paystack", content=body, headers=headers)
    assert first.status_code == 200 and first.json() == {"status": "received"}
    assert paystack.verified == [reference]
    assert store.get(f"subscriptions/{GUARDIAN}")["status"] == "active"
    # Paystack sends it again: nothing more happens.
    assert client.post("/webhooks/paystack", content=body, headers=headers).status_code == 200
    assert paystack.verified == [reference]


def test_a_webhook_that_failed_is_handled_again_when_paystack_resends_it(caplog):
    paystack = FakePaystack(paid=paid(), fail=True)
    client, store = make_client(settings=PAID, paystack=paystack)
    store.set("checkouts/pay_9", {"guardian_id": GUARDIAN, "plan_code": PLAN, "status": "STARTED"})
    body, headers = signed(charge_success("pay_9"))
    with caplog.at_level(logging.ERROR):
        client.post("/webhooks/paystack", content=body, headers=headers)
    [event] = [doc for p, doc in store.docs.items() if p.startswith("payment_events/")]
    assert event["status"] == "FAILED" and "guardian@example.com" not in caplog.text
    paystack.fail = False
    client.post("/webhooks/paystack", content=body, headers=headers)
    assert store.get(f"subscriptions/{GUARDIAN}")["status"] == "active"


def test_charge_success_for_an_unknown_reference_grants_nothing():
    client, store = make_client(settings=PAID, paystack=FakePaystack(paid=paid()))
    body, headers = signed(charge_success("pay_unknown"))
    assert client.post("/webhooks/paystack", content=body, headers=headers).status_code == 200
    [event] = [doc for p, doc in store.docs.items() if p.startswith("payment_events/")]
    assert event["status"] == "FAILED"
    assert not [p for p in store.docs if p.startswith("subscriptions/")]


def test_subscription_create_records_the_renewal_date():
    paystack = FakePaystack(paid=paid())
    client, store, response = started(paystack)
    client.post(f"/v1/checkout/{response.json()['reference']}/confirm", headers=bearer())
    event = {
        "event": "subscription.create",
        "data": {
            "subscription_code": "SUB_fictional001",
            "next_payment_date": "2026-02-14T09:00:00.000Z",
            "customer": {"customer_code": "CUS_fictional001"},
        },
    }
    body, headers = signed(event)
    client.post("/webhooks/paystack", content=body, headers=headers)
    subscription = store.get(f"subscriptions/{GUARDIAN}")
    SUBSCRIPTION.validate(subscription)
    assert subscription["subscription_code"] == "SUB_fictional001"
    assert subscription["current_period_end"] == "2026-02-14T09:00:00Z"
    # A later confirm keeps the subscription code.
    client.post(f"/v1/checkout/{response.json()['reference']}/confirm", headers=bearer())
    assert store.get(f"subscriptions/{GUARDIAN}")["subscription_code"] == "SUB_fictional001"


def test_subscription_create_for_an_unknown_customer_is_kept_as_failed():
    client, store = make_client(settings=PAID, paystack=FakePaystack())
    event = {
        "event": "subscription.create",
        "data": {"subscription_code": "SUB_x1", "customer": {}},
    }
    body, headers = signed(event)
    client.post("/webhooks/paystack", content=body, headers=headers)
    [doc] = [doc for p, doc in store.docs.items() if p.startswith("payment_events/")]
    assert doc["status"] == "FAILED"


def test_subscription_create_without_a_subscription_is_kept_as_failed():
    store = MemoryStore()
    store.set("paystack_customers/CUS_fictional001", {"guardian_id": GUARDIAN})
    client, store = make_client(settings=PAID, store=store, paystack=FakePaystack())
    event = {
        "event": "subscription.create",
        "data": {"subscription_code": "SUB_x1", "customer": {"customer_code": "CUS_fictional001"}},
    }
    body, headers = signed(event)
    client.post("/webhooks/paystack", content=body, headers=headers)
    [doc] = [doc for p, doc in store.docs.items() if p.startswith("payment_events/")]
    assert doc["status"] == "FAILED"


def test_other_events_are_acknowledged_and_ignored():
    client, store = make_client(settings=PAID, paystack=FakePaystack())
    body, headers = signed({"event": "invoice.update", "data": {"id": 7}})
    assert client.post("/webhooks/paystack", content=body, headers=headers).status_code == 200
    [doc] = [doc for p, doc in store.docs.items() if p.startswith("payment_events/")]
    assert doc["status"] == "IGNORED"


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]"])
def test_a_signed_body_that_is_not_an_event_is_a_400(body):
    client, _store = make_client(settings=PAID, paystack=FakePaystack())
    signature = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()
    reply = client.post(
        "/webhooks/paystack", content=body, headers={"x-paystack-signature": signature}
    )
    assert reply.status_code == 400


# ---- the plan's paywall (a server setting)


def with_plan(settings: AccountSettings, store: MemoryStore | None = None):
    store = store or MemoryStore()
    plan = json.loads((FIXTURES / "plan.sess_demo_001.json").read_text())
    store.set(f"plans/{plan['plan_id']}", plan)
    return make_client(settings=settings, store=store, paystack=FakePaystack(paid=paid()))


def test_with_the_paywall_off_every_guardian_sees_the_plan():
    client, _store = with_plan(PAID)
    assert client.get("/v1/plans/sess_demo_001", headers=bearer()).status_code == 200


def test_with_the_paywall_on_the_plan_comes_with_a_subscription():
    walled = dataclasses.replace(PAID, plans_need_subscription=True)
    client, store = with_plan(walled)
    refused = client.get("/v1/plans/sess_demo_001", headers=bearer())
    assert refused.status_code == 402 and refused.json()["error"]["code"] == "PAYMENT_REQUIRED"
    # Another guardian's plan is still a 404, not a 402: nothing leaks.
    assert client.get("/v1/plans/sess_demo_001", headers=bearer(oid=OTHER)).status_code == 404
    reference = client.post("/v1/checkout", headers=bearer()).json()["reference"]
    client.post(f"/v1/checkout/{reference}/confirm", headers=bearer())
    assert client.get("/v1/plans/sess_demo_001", headers=bearer()).status_code == 200
    assert (
        client.get("/v1/subscription", headers=bearer()).json()["plans_need_subscription"] is True
    )


# ---- settings


def env(**changes) -> dict:
    return {
        "ENTRA_TENANT_ID": "t",
        "ENTRA_AUTHORITY": "https://aloai.ciamlogin.com",
        "ENTRA_API_AUDIENCE": "a",
    } | changes


def test_settings_read_paystack_and_the_paywall():
    settings = AccountSettings.from_env(
        env(PAYSTACK_SECRET_KEY=SECRET, PAYSTACK_PLAN_CODE=PLAN, PLANS_NEED_SUBSCRIPTION="true"),
        hosted=False,
    )
    assert settings.payments_on and settings.plans_need_subscription
    assert settings.plan_amount_kobo == 150000
    assert not AccountSettings.from_env(env(), hosted=False).payments_on


def test_a_live_paystack_key_is_refused_unless_live_is_switched_on():
    with pytest.raises(ConfigError, match="test key"):
        AccountSettings.from_env(env(PAYSTACK_SECRET_KEY="sk_live_x"), hosted=False)
    settings = AccountSettings.from_env(
        env(PAYSTACK_SECRET_KEY="sk_live_x", PAYSTACK_LIVE="true"), hosted=False
    )
    assert settings.paystack_secret_key == "sk_live_x"


def test_the_paywall_setting_must_be_true_or_false():
    with pytest.raises(ConfigError, match="PLANS_NEED_SUBSCRIPTION"):
        AccountSettings.from_env(env(PLANS_NEED_SUBSCRIPTION="yes"), hosted=False)


# ---- the Paystack client and the signature


def test_the_signature_is_the_hmac_sha512_of_the_raw_body():
    body = b'{"event":"charge.success"}'
    good = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()
    assert signature_ok(SECRET, body, good)
    assert not signature_ok(SECRET, body + b" ", good)
    assert not signature_ok(SECRET, body, None)


class Opener:
    def __init__(self, reply: bytes | Exception) -> None:
        self.reply = reply
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        if isinstance(self.reply, Exception):
            raise self.reply
        return io.BytesIO(self.reply)


def test_the_client_initializes_with_the_plan_and_the_secret_as_a_bearer():
    opener = Opener(json.dumps({"status": True, "data": {"access_code": "c"}}).encode())
    data = PaystackApi(SECRET, opener).initialize(
        email="guardian@example.com", plan=PLAN, amount_kobo=150000, reference="pay_1", metadata={}
    )
    assert data == {"access_code": "c"}
    [(request, timeout)] = opener.requests
    assert request.full_url == "https://api.paystack.co/transaction/initialize"
    assert request.get_header("Authorization") == f"Bearer {SECRET}"
    assert json.loads(request.data)["plan"] == PLAN and timeout == 10


def test_the_client_verifies_by_reference():
    opener = Opener(json.dumps({"status": True, "data": {"status": "success"}}).encode())
    assert PaystackApi(SECRET, opener).verify("pay_1/../x")["status"] == "success"
    [(request, _)] = opener.requests
    assert request.full_url == "https://api.paystack.co/transaction/verify/pay_1%2F..%2Fx"
    assert request.get_method() == "GET"


@pytest.mark.parametrize(
    "reply, reason",
    [
        (json.dumps({"status": False, "message": "Invalid key"}).encode(), "not a success"),
        (json.dumps({"status": True}).encode(), "no data"),
        (b"<html>", "JSONDecodeError"),
        (urllib.error.HTTPError("u", 401, "Unauthorized", {}, None), "HTTP 401"),
        (urllib.error.URLError("down"), "URLError"),
        (TimeoutError(), "TimeoutError"),
    ],
)
def test_the_client_turns_any_failure_into_a_short_paystack_error(reply, reason):
    with pytest.raises(PaystackError) as raised:
        PaystackApi(SECRET, Opener(reply)).verify("pay_1")
    assert str(raised.value) == reason


def test_the_now_is_used_for_the_paid_at_when_paystack_gives_none():
    client, store, response = started(FakePaystack(paid=paid(paid_at=None)))
    client.post(f"/v1/checkout/{response.json()['reference']}/confirm", headers=bearer())
    assert store.get(f"subscriptions/{GUARDIAN}")["paid_at"] == NOW.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_a_charge_while_the_paystack_client_is_off_is_kept_as_failed():
    store = MemoryStore()
    store.set("checkouts/pay_9", {"guardian_id": GUARDIAN, "plan_code": PLAN, "status": "STARTED"})
    client, store = make_client(settings=PAID, store=store, paystack=None)
    body, headers = signed(charge_success("pay_9"))
    client.post("/webhooks/paystack", content=body, headers=headers)
    [doc] = [doc for p, doc in store.docs.items() if p.startswith("payment_events/")]
    assert (doc["status"], doc["error"]) == ("FAILED", "PaystackError")
