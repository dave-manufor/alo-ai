"""The parent subscription in Paystack test mode (PRD 11.1, 14.1): checkout, the webhook, and the
entitlement in subscriptions/{guardian_id}.

- POST /v1/checkout: records checkouts/{reference} for this guardian first, then initializes a
  Paystack transaction with the plan code, so the reference always leads back to the guardian
  and the browser can change neither amount nor plan. Paystack gets the guardian's email only,
  never anything about a child. The web app opens Paystack's popup with the access code.
- POST /v1/checkout/{reference}/confirm: after the popup says it is paid, the server asks
  Paystack (Verify Transaction) before granting anything. The same grant runs from the webhook,
  so whichever comes first unlocks the plan and the other changes nothing.
- POST /webhooks/paystack: the x-paystack-signature (HMAC-SHA512 of the raw body) is checked
  before anything else; a forged one is a 401. It answers 200 at once and handles the event
  after; each event is handled once (payment_events/{id}), or again only if it failed.
  charge.success is verified with Paystack before access is granted; subscription.create
  records the renewal date.
- GET /v1/subscription: whether this guardian is subscribed, and whether the plan needs it.

No agent reaches these routes, nothing here makes a score, and the secret key and the emails
are never logged.
"""

import hashlib
import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Annotated, Any

from aloai_contracts import CHECKOUT_START, SUBSCRIPTION, SUBSCRIPTION_STATUS
from aloai_store import Store
from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request
from fastapi.responses import JSONResponse

from .access import Clock, NewId, audit, ensure_guardian, not_found, stamp, utc_now
from .auth import Principal
from .children import default_id
from .errors import AccountError
from .paystack import Paystack, PaystackError, signature_ok
from .settings import AccountSettings

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
# Until Paystack's subscription.create gives the next payment date, a paid month runs this long.
PAID_PERIOD = timedelta(days=31)
_REFERENCE = re.compile(r"[A-Za-z0-9_-]{1,64}")


def unavailable() -> AccountError:
    return AccountError(
        503, "PAYMENTS_UNAVAILABLE", "Payment is not open just now.", retryable=True
    )


class Subscriptions:
    """The entitlements, and the one way access is granted: a transaction Paystack says is paid."""

    def __init__(
        self, store: Store, paystack: Paystack | None, settings: AccountSettings, now: Clock
    ) -> None:
        self.store, self.paystack, self.settings, self.now = store, paystack, settings, now

    def active(self, guardian_id: str) -> bool:
        subscription = self.store.get(f"subscriptions/{guardian_id}")
        if not subscription or subscription.get("status") != "active":
            return False
        return subscription["current_period_end"] > stamp(self.now())

    def status(self, guardian_id: str) -> dict[str, Any]:
        subscription = self.store.get(f"subscriptions/{guardian_id}") or {}
        reply = {
            "schema_version": SCHEMA_VERSION,
            "active": self.active(guardian_id),
            "plans_need_subscription": self.settings.plans_need_subscription,
            "current_period_end": subscription.get("current_period_end"),
        }
        SUBSCRIPTION_STATUS.validate(reply)
        return reply

    def plan_open(self, guardian_id: str) -> bool:
        return not self.settings.plans_need_subscription or self.active(guardian_id)

    def grant(self, reference: str) -> bool:
        """Ask Paystack whether this checkout's transaction is paid; if it is, the guardian who
        started it is subscribed. True when access is (now) granted. Running it again with the
        same reference changes nothing."""
        checkout = self.store.get(f"checkouts/{reference}")
        if checkout is None:
            raise LookupError("no checkout with that reference")
        if self.paystack is None:
            raise PaystackError("payments are off")
        data = self.paystack.verify(reference)
        paid = (
            data.get("status") == "success"
            and data.get("reference") == reference
            and data.get("currency") == "NGN"
            and _plan_code(data) == checkout["plan_code"]
        )
        if not paid:
            return False
        guardian_id = checkout["guardian_id"]
        paid_at = data.get("paid_at") or stamp(self.now())
        current = self.store.get(f"subscriptions/{guardian_id}") or {}
        period_end = max(
            current.get("current_period_end") or "",
            stamp(_parse(paid_at) + PAID_PERIOD),
        )
        subscription = {
            "schema_version": SCHEMA_VERSION,
            "guardian_id": guardian_id,
            "status": "active",
            "plan_code": checkout["plan_code"],
            "last_reference": reference,
            "paid_at": stamp(_parse(paid_at)),
            "current_period_end": period_end,
            "updated_at": stamp(self.now()),
        }
        customer = (data.get("customer") or {}).get("customer_code")
        if customer:
            subscription["customer_code"] = customer
            self.store.set(f"paystack_customers/{customer}", {"guardian_id": guardian_id})
        if current.get("subscription_code"):
            subscription["subscription_code"] = current["subscription_code"]
        SUBSCRIPTION.validate(subscription)
        self.store.set(f"subscriptions/{guardian_id}", subscription)
        self.store.merge(f"checkouts/{reference}", {"status": "PAID"})
        return True

    def record_subscription(self, data: dict) -> None:
        """subscription.create: the Paystack subscription and its next payment date, for the
        guardian whose payment made it (found by the Paystack customer)."""
        customer = (data.get("customer") or {}).get("customer_code")
        known = self.store.get(f"paystack_customers/{customer}") if customer else None
        if known is None:
            raise LookupError("no guardian for that Paystack customer")
        path = f"subscriptions/{known['guardian_id']}"
        current = self.store.get(path)
        if current is None:
            raise LookupError("no subscription to add it to")
        changes = {"subscription_code": data["subscription_code"], "updated_at": stamp(self.now())}
        if data.get("next_payment_date"):
            changes["current_period_end"] = stamp(_parse(data["next_payment_date"]))
        SUBSCRIPTION.validate(current | changes)
        self.store.merge(path, changes)


def router(
    store: Store,
    guardian: Callable[..., Principal],
    subscriptions: Subscriptions,
    settings: AccountSettings,
    now: Clock = utc_now,
    new_id: NewId = default_id,
) -> APIRouter:
    routes = APIRouter()
    current = Depends(guardian)
    paystack = subscriptions.paystack

    @routes.get("/v1/subscription")
    def subscription(principal: Annotated[Principal, current]) -> dict[str, Any]:
        return subscriptions.status(principal.guardian_id)

    @routes.post("/v1/checkout", status_code=201)
    def start_checkout(principal: Annotated[Principal, current]) -> dict[str, Any]:
        if paystack is None or not settings.payments_on:
            raise unavailable()
        me = ensure_guardian(store, principal, now)
        if subscriptions.active(principal.guardian_id):
            raise AccountError(409, "ALREADY_SUBSCRIBED", "You already have the weekly plan.")
        reference = new_id("pay")
        store.set(
            f"checkouts/{reference}",
            {
                "guardian_id": principal.guardian_id,
                "plan_code": settings.paystack_plan_code,
                "status": "STARTED",
                "created_at": stamp(now()),
            },
        )
        try:
            started = paystack.initialize(
                email=me["email"],
                plan=settings.paystack_plan_code,
                amount_kobo=settings.plan_amount_kobo,
                reference=reference,
                metadata={"guardian_id": principal.guardian_id},
            )
        except PaystackError as error:
            log.error("could not start a checkout: %s", error)
            raise unavailable() from None
        audit(store, principal, "checkout.start", {"reference": reference}, now, new_id)
        reply = {
            "schema_version": SCHEMA_VERSION,
            "reference": reference,
            "access_code": started["access_code"],
            "authorization_url": started["authorization_url"],
        }
        CHECKOUT_START.validate(reply)
        return reply

    @routes.post("/v1/checkout/{reference}/confirm")
    def confirm_checkout(reference: str, principal: Annotated[Principal, current]) -> dict:
        if not _REFERENCE.fullmatch(reference):
            raise not_found()
        checkout = store.get(f"checkouts/{reference}")
        if checkout is None or checkout.get("guardian_id") != principal.guardian_id:
            raise not_found()
        try:
            subscriptions.grant(reference)
        except PaystackError as error:
            log.error("could not verify a checkout: %s", error)
            raise unavailable() from None
        audit(store, principal, "checkout.confirm", {"reference": reference}, now, new_id)
        return subscriptions.status(principal.guardian_id)

    @routes.post("/webhooks/paystack")
    async def paystack_webhook(
        request: Request,
        background: BackgroundTasks,
        x_paystack_signature: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        body = await request.body()
        secret = settings.paystack_secret_key
        if not secret or not signature_ok(secret, body, x_paystack_signature):
            raise AccountError(401, "INVALID_SIGNATURE", "That request is not from Paystack.")
        try:
            event = json.loads(body)
        except ValueError:
            raise AccountError(400, "INVALID_REQUEST", "That is not an event.") from None
        if not isinstance(event, dict):
            raise AccountError(400, "INVALID_REQUEST", "That is not an event.")
        background.add_task(handle_event, event)
        return JSONResponse({"status": "received"})

    def handle_event(event: dict) -> None:
        """One Paystack event, once: a repeat of one that succeeded changes nothing."""
        kind = str(event.get("event"))
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        key = data.get("reference") or data.get("subscription_code") or data.get("id")
        event_id = hashlib.sha256(f"{kind}:{key}".encode()).hexdigest()[:40]
        path = f"payment_events/{event_id}"
        if not store.create(path, {"event": kind, "status": "RECEIVED", "at": stamp(now())}):
            if (store.get(path) or {}).get("status") != "FAILED":
                return  # handled already
        try:
            match kind:
                case "charge.success":
                    subscriptions.grant(str(data["reference"]))
                case "subscription.create":
                    subscriptions.record_subscription(data)
                case _:
                    store.merge(path, {"status": "IGNORED"})
                    return
        except (PaystackError, LookupError, ValueError) as error:
            # The class only: an error's text can hold the event, which carries an email.
            log.error("paystack %s not handled: %s", kind, type(error).__name__)
            store.merge(path, {"status": "FAILED", "error": type(error).__name__})
            return
        store.merge(path, {"status": "DONE"})

    return routes


def _plan_code(data: dict) -> str | None:
    """The plan of a verified transaction: Paystack gives its code, or the plan object."""
    plan = data.get("plan")
    if isinstance(plan, dict):
        return plan.get("plan_code")
    if isinstance(plan, str) and plan:
        return plan
    plan_object = data.get("plan_object")
    return plan_object.get("plan_code") if isinstance(plan_object, dict) else None


def _parse(moment: str) -> datetime:
    return datetime.fromisoformat(moment.replace("Z", "+00:00"))
