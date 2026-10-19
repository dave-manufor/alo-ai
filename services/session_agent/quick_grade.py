"""Client side of POST /v1/grade:quick (PRD 7.4, SDD 7; contract owned by W3).

One call per scored turn: the retell (index 0) and every question, including one
the child did not answer, which is sent with an empty transcript and scored 0
without a model call. The response carries the listening decision once the retell
and every item are in; only that complete response reaches the machine. A late,
pending or failed call is covered by the machine's 6 s quick_score timer.

    request  {schema_version, session_id, passage_id, turn_phase, index, transcript}
    response {schema_version, complete, run_listening_module} | {error: {...}}
"""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

SCHEMA_VERSION = 1
PATH = "/v1/grade:quick"
TIMEOUT_S = 3.0  # per attempt; one retry fits inside the machine's 6 s quick_score timer
TOKEN_TTL_S = 50 * 60  # Cloud Run ID tokens last about an hour; renew early


def request_body(
    session_id: str, passage_id: str, turn_phase: str, index: int, transcript: str
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "passage_id": passage_id,
        "turn_phase": turn_phase,
        "index": index,
        "transcript": transcript,
    }


def decision(response: dict) -> bool | None:
    """run_listening_module from a complete response; None for pending, error or junk."""
    if response.get("complete") is not True:
        return None
    run = response.get("run_listening_module")
    return run if isinstance(run, bool) else None


@dataclass
class FixtureQuickGrader:
    """AI_MODE=fixtures: answers like the endpoint, from a fixed decision.

    complete once the retell and `items` questions have been sent. The decision
    comes from fixtures/ai/quick/{passage_id}.json ({"run_listening_module": bool})
    when present, else `default`.
    """

    items: int
    fixtures_dir: Path | None = None
    default: bool = False
    seen: set[tuple[str, int]] = field(default_factory=set)

    def answer(self, body: dict) -> dict:
        self.seen.add((body["turn_phase"], body["index"]))
        needed = {("RETELL", 0), *(("QUESTION", n) for n in range(self.items))}
        if not needed <= self.seen:
            return {
                "schema_version": SCHEMA_VERSION,
                "complete": False,
                "run_listening_module": None,
            }
        return {
            "schema_version": SCHEMA_VERSION,
            "complete": True,
            "run_listening_module": self._decision(body["passage_id"]),
        }

    def _decision(self, passage_id: str) -> bool:
        if self.fixtures_dir is not None:
            path = self.fixtures_dir / f"{passage_id}.json"
            if path.exists():
                return bool(json.loads(path.read_text())["run_listening_module"])
        return self.default


def _error(code: str, message: str, *, retryable: bool) -> dict:
    return {"error": {"code": code, "message": message, "retryable": retryable}}


def _retryable(response: dict) -> bool:
    error = response.get("error")
    return isinstance(error, dict) and error.get("retryable") is True


class QuickGradeClient:
    """AI_MODE=live: POST to Core with a Cloud Run ID token. Errors come back as SDD 11 errors.

    One HTTP client and one ID token serve the whole session, so a call costs no new TLS
    handshake and no token fetch (the token is valid for about an hour; the fetch is a
    blocking call, so it runs in a thread). A retryable error is tried once more: each
    attempt gets TIMEOUT_S and two fit inside the machine's 6 s quick_score timer, which
    runs the listening module if no complete answer arrives in time.
    """

    def __init__(
        self,
        base_url: str,
        token: Callable[[], str] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}{PATH}"
        self._fetch_token, self._client, self._clock = token, client, clock
        self._token: str | None = None
        self._token_expires = 0.0
        self._token_lock = asyncio.Lock()

    async def post(self, body: dict) -> dict:
        response = await self._attempt(body)
        if _retryable(response):
            response = await self._attempt(body)
        return response

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def _attempt(self, body: dict) -> dict:
        try:
            headers = await self._headers()
        except Exception as error:  # noqa: BLE001 - no ID token is an error reply, not a crash
            return _error("AUTH", f"could not get an ID token: {error}", retryable=False)
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=TIMEOUT_S)
        try:
            reply = await self._client.post(self._url, json=body, headers=headers)
        except httpx.HTTPError as error:
            return _error("CLIENT", str(error) or type(error).__name__, retryable=True)
        if reply.status_code in (401, 403):
            self._token = None  # expired or revoked early: fetch a new one next time
        try:
            data = reply.json()
        except ValueError:
            return _error("CLIENT", f"not JSON (HTTP {reply.status_code})", retryable=True)
        if not isinstance(data, dict):
            return _error("CLIENT", f"unexpected reply (HTTP {reply.status_code})", retryable=True)
        return data

    async def _headers(self) -> dict[str, str]:
        if self._fetch_token is None:
            return {}
        async with self._token_lock:
            if self._token is None or self._clock() >= self._token_expires:
                self._token = await asyncio.to_thread(self._fetch_token)
                self._token_expires = self._clock() + TOKEN_TTL_S
            return {"Authorization": f"Bearer {self._token}"}
