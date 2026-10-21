"""Calls from the Session Agent to Core (SDD 11), with a Cloud Run ID token.

Errors come back as SDD 11 errors ({error: {code, message, retryable}}), never as
exceptions, so a caller only checks the reply. One HTTP client and one ID token serve
the whole session, so a call costs no new TLS handshake and no token fetch (the token
is valid for about an hour; the fetch is a blocking call, so it runs in a thread).
"""

import asyncio
import time
from collections.abc import Callable

import httpx

TOKEN_TTL_S = 50 * 60  # Cloud Run ID tokens last about an hour; renew early


def _error(code: str, message: str, *, retryable: bool) -> dict:
    return {"error": {"code": code, "message": message, "retryable": retryable}}


def _retryable(response: dict) -> bool:
    error = response.get("error")
    return isinstance(error, dict) and error.get("retryable") is True


class CoreClient:
    """POST to one Core route. Each attempt gets timeout_s; with retry, a retryable
    error is tried once more."""

    def __init__(
        self,
        base_url: str,
        path: str,
        timeout_s: float,
        token: Callable[[], str] | None = None,
        *,
        retry: bool = False,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}{path}"
        self._timeout_s, self._retry = timeout_s, retry
        self._fetch_token, self._client, self._clock = token, client, clock
        self._token: str | None = None
        self._token_expires = 0.0
        self._token_lock = asyncio.Lock()

    async def post(self, body: dict) -> dict:
        response = await self._attempt(body)
        if self._retry and _retryable(response):
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
            self._client = httpx.AsyncClient(timeout=self._timeout_s)
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
