"""Children and their consent (PRD 12, SDD 12). A child and the guardian's consent for that
child are recorded in one step; without the attestation nothing is saved. Consent is
append-only: a new consent never replaces an earlier one, and there is no withdrawal in v1
(a guardian who withdraws is handled by ops/delete_child.py)."""

import uuid
from collections.abc import Callable
from typing import Annotated, Any

from aloai_contracts import CHILD, CONSENT
from aloai_store import Store
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .access import (
    Clock,
    NewId,
    audit,
    ensure_guardian,
    not_found,
    owned_child,
    stamp,
    utc_now,
)
from .auth import Principal
from .consent import CONSENT_VERSION, attestation_for
from .errors import AccountError


def default_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class NewChild(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_name: str = Field(min_length=1, max_length=40)
    primary_class: int = Field(ge=1, le=6)
    birth_year: int = Field(ge=2000, le=2100)
    attested: bool
    training_opt_in: bool = False

    @field_validator("first_name")
    @classmethod
    def trimmed(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("first_name must not be blank")
        return value


class ChildEdit(BaseModel):
    """What a guardian may change on a child. Anything not listed is refused, and at least one
    thing must be sent. Consent is not touched: it is append-only."""

    model_config = ConfigDict(extra="forbid")
    first_name: str | None = Field(default=None, min_length=1, max_length=40)
    primary_class: int | None = Field(default=None, ge=1, le=6)
    birth_year: int | None = Field(default=None, ge=2000, le=2100)

    @field_validator("first_name")
    @classmethod
    def trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("first_name must not be blank")
        return value


class NewConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    child_id: str = Field(min_length=1, max_length=64)
    attested: bool
    training_opt_in: bool = False


def router(
    store: Store,
    guardian: Callable[..., Principal],
    now: Clock = utc_now,
    new_id: NewId = default_id,
) -> APIRouter:
    routes = APIRouter()
    current = Depends(guardian)

    def consent_for(principal: Principal, child_id: str, child: dict, attested: bool, opt_in: bool):
        if not attested:
            raise AccountError(
                400, "CONSENT_REQUIRED", "Consent is needed before adding a child.", retryable=False
            )
        guardian = ensure_guardian(store, principal, now)
        moment = now()
        document = {
            "schema_version": 1,
            "consent_id": new_id("consent"),
            "guardian_id": principal.guardian_id,
            "child_id": child_id,
            "text_version": CONSENT_VERSION,
            "attestation": attestation_for(child["first_name"], moment.year - child["birth_year"]),
            "sign_in_method": principal.sign_in_method,
            "verified_email": guardian["email"],
            "timestamp": stamp(moment),
            "training_opt_in": opt_in,
        }
        CONSENT.validate(document)
        store.create(f"consents/{document['consent_id']}", document)
        audit(store, principal, "consent.create", {"child_id": child_id}, now, new_id)
        return document

    def consents_of(child_id: str) -> list[dict]:
        found = store.where("consents", "child_id", child_id)
        return sorted(found, key=lambda consent: consent["timestamp"])

    @routes.post("/v1/children", status_code=201)
    def add_child(body: NewChild, principal: Annotated[Principal, current]) -> dict[str, Any]:
        ensure_guardian(store, principal, now)
        moment = now()
        child_id = new_id("child")
        child = {
            "schema_version": 1,
            "guardian_id": principal.guardian_id,
            "first_name": body.first_name,
            "primary_class": body.primary_class,
            "birth_year": body.birth_year,
            "class_confirmed_year": moment.year,
            "created_at": stamp(moment),
        }
        CHILD.validate(child)
        consent = consent_for(principal, child_id, child, body.attested, body.training_opt_in)
        store.create(f"children/{child_id}", child)
        audit(store, principal, "child.create", {"child_id": child_id}, now, new_id)
        return {"child_id": child_id, "child": child, "consent": consent}

    @routes.get("/v1/children")
    def list_children(principal: Annotated[Principal, current]) -> dict[str, Any]:
        # A child always has a consent, so the guardian's consents name their children.
        mine = store.where("consents", "guardian_id", principal.guardian_id)
        ids = sorted({consent["child_id"] for consent in mine})
        documents = store.get_many([f"children/{child_id}" for child_id in ids])
        return {
            "children": [
                {"child_id": child_id, **document}
                for child_id, document in zip(ids, documents, strict=True)
                if document is not None and document["guardian_id"] == principal.guardian_id
            ]
        }

    @routes.get("/v1/children/{child_id}")
    def get_child(child_id: str, principal: Annotated[Principal, current]) -> dict[str, Any]:
        return {"child_id": child_id, **owned_child(store, principal, child_id)}

    @routes.patch("/v1/children/{child_id}")
    def edit_child(
        child_id: str, body: ChildEdit, principal: Annotated[Principal, current]
    ) -> dict[str, Any]:
        child = owned_child(store, principal, child_id)
        changes = body.model_dump(exclude_none=True)
        if not changes:
            raise AccountError(
                400, "INVALID_REQUEST", "Please say what to change.", retryable=False
            )
        if "primary_class" in changes:
            # The guardian has just confirmed the class (each September we ask again).
            changes["class_confirmed_year"] = now().year
        CHILD.validate(child | changes)
        store.merge(f"children/{child_id}", changes)
        audit(
            store,
            principal,
            "child.update",
            {"child_id": child_id, "fields": sorted(changes)},
            now,
            new_id,
        )
        return {"child_id": child_id, **child, **changes}

    @routes.get("/v1/children/{child_id}/consent")
    def get_consent(child_id: str, principal: Annotated[Principal, current]) -> dict[str, Any]:
        owned_child(store, principal, child_id)
        found = [c for c in consents_of(child_id) if c["guardian_id"] == principal.guardian_id]
        if not found:
            raise not_found()
        return found[-1]

    @routes.post("/v1/consents", status_code=201)
    def add_consent(body: NewConsent, principal: Annotated[Principal, current]) -> dict[str, Any]:
        child = owned_child(store, principal, body.child_id)
        return consent_for(principal, body.child_id, child, body.attested, body.training_opt_in)

    return routes
