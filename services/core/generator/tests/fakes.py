"""A scripted model and a fake clock for the Writer, Critic and loop tests."""

import copy
import json
import threading
from pathlib import Path

from services.core.generator.models import ModelCall

ROOT = Path(__file__).resolve().parents[4]
RECORDED = ROOT / "fixtures" / "ai" / "generator"
DEMO = json.loads((RECORDED / "sess_demo_001.json").read_text(encoding="utf-8"))
CONTRACTS = ROOT / "fixtures" / "contracts"


def demo(key: str) -> dict:
    """A deep copy of one recorded response of the demo session."""
    return copy.deepcopy(DEMO[key])


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class ScriptedModel:
    """Answers each call from responses[key]: a dict, or an exception to raise. Every
    call is kept, and each one moves the clock on by its seconds[role], if any."""

    def __init__(
        self,
        responses: dict,
        clock: Clock | None = None,
        seconds: dict[str, float] | None = None,
    ) -> None:
        self.responses = responses
        self.clock = clock
        self.seconds = seconds or {}
        self.calls: list[ModelCall] = []
        self._lock = threading.Lock()

    def call(self, call: ModelCall) -> dict:
        with self._lock:
            self.calls.append(call)
            if self.clock is not None:
                self.clock.t += self.seconds.get(call.key.split("/")[0], 0.0)
        answer = self.responses[call.key]
        if isinstance(answer, Exception):
            raise answer
        return copy.deepcopy(answer)

    def keys(self) -> list[str]:
        return [call.key for call in self.calls]

    def prompt(self, key: str) -> str:
        return next(call.prompt for call in self.calls if call.key == key)


def demo_responses(attempts: int = 1) -> dict:
    """The demo session's recorded answers for each attempt."""
    responses = {}
    for attempt in range(1, attempts + 1):
        for role in ("writer", "critic_a", "critic_b", "critic_c"):
            responses[f"{role}/{attempt}"] = demo(f"{role}/1")
    return responses
