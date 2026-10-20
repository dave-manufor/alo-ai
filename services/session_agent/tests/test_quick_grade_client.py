"""QuickGradeClient: one HTTP client, one cached ID token, one retry on a retryable error."""

import asyncio

import httpx
from services.session_agent import quick_grade
from services.session_agent.quick_grade import (
    PATH,
    TOKEN_TTL_S,
    QuickGradeClient,
    request_body,
)

BODY = request_body("sess_demo_001", "bank_p3_market_day", "QUESTION", 0, "Ada chose a hat")
COMPLETE = {"schema_version": 1, "complete": True, "run_listening_module": False}
GRADING_FAILED = {
    "error": {"code": "GRADING_FAILED", "message": "model unavailable", "retryable": True}
}
UNKNOWN_ITEM = {"error": {"code": "UNKNOWN_ITEM", "message": "no item 2", "retryable": False}}


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


class Tokens:
    def __init__(self) -> None:
        self.fetched = 0

    def __call__(self) -> str:
        self.fetched += 1
        return f"token-{self.fetched}"


def served(*replies):
    """A client answering with each reply in turn (the last repeats); records the requests."""
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        reply = replies[min(len(requests), len(replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx.Response):
            return reply
        status, body = reply
        return httpx.Response(status, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


def post(client, token=None, *, clock=None, calls=1):
    async def main():
        grader = QuickGradeClient(
            "https://core.example/", token, client=client, clock=clock or Clock()
        )
        replies = [await grader.post(BODY) for _ in range(calls)]
        await grader.aclose()
        return replies

    return asyncio.run(main())


def test_the_request_goes_to_the_quick_endpoint_with_the_id_token():
    client, requests = served((200, COMPLETE))
    assert post(client, Tokens()) == [COMPLETE]
    assert str(requests[0].url) == f"https://core.example{PATH}"
    assert requests[0].headers["Authorization"] == "Bearer token-1"
    assert requests[0].read() == httpx.Request("POST", "http://x", json=BODY).read()


def test_locally_there_is_no_token_and_no_authorization_header():
    client, requests = served((200, COMPLETE))
    assert post(client, None) == [COMPLETE]
    assert "Authorization" not in requests[0].headers


def test_the_id_token_is_fetched_once_and_reused():
    client, requests = served((200, COMPLETE))
    tokens = Tokens()
    post(client, tokens, calls=3)
    assert tokens.fetched == 1
    assert {r.headers["Authorization"] for r in requests} == {"Bearer token-1"}


def test_the_id_token_is_renewed_before_it_expires():
    client, requests = served((200, COMPLETE))
    tokens, clock = Tokens(), Clock()

    async def main():
        grader = QuickGradeClient("https://core.example", tokens, client=client, clock=clock)
        await grader.post(BODY)
        clock.now += TOKEN_TTL_S - 1
        await grader.post(BODY)
        clock.now += 2
        await grader.post(BODY)

    asyncio.run(main())
    assert tokens.fetched == 2
    assert [r.headers["Authorization"] for r in requests] == [
        "Bearer token-1",
        "Bearer token-1",
        "Bearer token-2",
    ]


def test_a_rejected_token_is_replaced_on_the_next_call():
    client, requests = served((401, {"message": "expired"}), (200, COMPLETE))
    tokens = Tokens()
    replies = post(client, tokens, calls=2)
    assert replies[1] == COMPLETE
    assert tokens.fetched == 2
    assert requests[1].headers["Authorization"] == "Bearer token-2"


def test_a_retryable_error_is_tried_once_more():
    client, requests = served((502, GRADING_FAILED), (200, COMPLETE))
    assert post(client) == [COMPLETE]
    assert len(requests) == 2


def test_a_retryable_error_that_repeats_is_returned_after_one_retry():
    client, requests = served((502, GRADING_FAILED))
    assert post(client) == [GRADING_FAILED]
    assert len(requests) == 2


def test_a_refusal_is_not_retried():
    client, requests = served((400, UNKNOWN_ITEM))
    assert post(client) == [UNKNOWN_ITEM]
    assert len(requests) == 1


def test_a_lost_connection_becomes_a_retryable_client_error_after_one_retry():
    client, requests = served(httpx.ConnectError("connection refused"))
    [reply] = post(client)
    assert reply["error"] == {
        "code": "CLIENT",
        "message": "connection refused",
        "retryable": True,
    }
    assert len(requests) == 2


def test_a_reply_that_is_not_a_json_object_is_a_client_error():
    html, requests = served(httpx.Response(502, text="<html>Bad Gateway</html>"))
    [reply] = post(html)
    assert reply["error"]["code"] == "CLIENT"
    assert "HTTP 502" in reply["error"]["message"]
    assert len(requests) == 2
    listed, _ = served((200, [1, 2]))
    assert post(listed)[0]["error"]["code"] == "CLIENT"


def test_no_id_token_is_an_error_reply_not_a_crash():
    def broken() -> str:
        raise RuntimeError("metadata server unreachable")

    client, requests = served((200, COMPLETE))
    [reply] = post(client, broken)
    assert reply["error"]["code"] == "AUTH"
    assert reply["error"]["retryable"] is False
    assert requests == []


def test_without_a_client_one_is_made_once_with_the_attempt_timeout_and_closed(monkeypatch):
    made = []
    mock, requests = served((200, COMPLETE))

    def make(**kwargs):
        made.append(kwargs)
        return mock

    monkeypatch.setattr(quick_grade.httpx, "AsyncClient", make)

    async def main():
        grader = QuickGradeClient("https://core.example")
        await grader.aclose()  # nothing opened yet
        replies = [await grader.post(BODY), await grader.post(BODY)]
        await grader.aclose()
        return replies

    assert asyncio.run(main()) == [COMPLETE, COMPLETE]
    assert made == [{"timeout": quick_grade.TIMEOUT_S}]
    assert len(requests) == 2
    assert mock.is_closed
