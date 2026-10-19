"""Client side of POST /v1/grade:quick (PRD 7.4, SDD 7; contract owned by W3).

One call per scored turn: the retell (index 0) and every question, including one
the child did not answer, which is sent with an empty transcript and scored 0
without a model call. The response carries the listening decision once the retell
and every item are in; only that complete response reaches the machine. A late,
pending or failed call is covered by the machine's 6 s quick_score timer.

    request  {schema_version, session_id, passage_id, turn_phase, index, transcript}
    response {schema_version, complete, run_listening_module} | {error: {...}}
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1
PATH = "/v1/grade:quick"
TIMEOUT_S = 6.0


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


async def post(
    base_url: str, body: dict, token: Callable[[], str] | None = None
) -> dict:  # pragma: no cover - network; exercised in the end-to-end run
    """AI_MODE=live: POST with a Cloud Run ID token. Errors come back as SDD 11 errors."""
    import httpx

    headers = {"Authorization": f"Bearer {token()}"} if token else {}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            reply = await client.post(f"{base_url.rstrip('/')}{PATH}", json=body, headers=headers)
        return reply.json()
    except (httpx.HTTPError, ValueError) as error:
        return {"error": {"code": "CLIENT", "message": str(error), "retryable": True}}
