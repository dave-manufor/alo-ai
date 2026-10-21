"""The model calls of the Story Writer and the Critic (PRD 4.5 G2, G4).

VertexModel calls Gemini on Vertex AI with a JSON response schema. FixtureModel answers
from the recorded responses in fixtures/ai/generator/{session_id}.json, keyed by the
call's key (e.g. "writer/1", "critic_b/2"), so laptops and CI never reach Vertex
(AI_MODE=fixtures). Same shape as services/core/grader/models.py.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

FLASH = "gemini-2.5-flash"


@dataclass(frozen=True)
class ModelCall:
    """One model call. key names it among the recorded responses."""

    key: str
    session_id: str
    model: str
    prompt: str
    response_schema: dict
    timeout_s: float
    temperature: float = 0


class ModelError(Exception):
    """The model gave no usable answer for the call."""


# Vertex AI or Azure OpenAI did not answer, or not in time: worth a retry later, unlike a
# bad answer. The Gemini client raises httpx's own errors for a timeout; the OpenAI client
# its own APIError family (a timeout and a refused connection included).
def _upstream_errors() -> tuple[type[Exception], ...]:
    """Each cloud's SDK errors, for the SDKs that are installed (an image carries only its own)."""
    errors: tuple[type[Exception], ...] = (genai_errors.APIError, httpx.HTTPError)
    try:
        from azure.core.exceptions import AzureError
        from openai import APIError as OpenAIError
    except ImportError:
        return errors
    return (*errors, OpenAIError, AzureError)


UpstreamErrors = _upstream_errors()


class Model(Protocol):
    def call(self, call: ModelCall) -> dict: ...


class VertexModel:
    def __init__(self, client: genai.Client) -> None:
        self._client = client

    def call(self, call: ModelCall) -> dict:
        # No thinking: the Writer and three Critic calls share a 20 s deadline. If the
        # gate pass rate is too low, the evaluation set decides between thinking and Pro.
        config = types.GenerateContentConfig(
            temperature=call.temperature,
            response_mime_type="application/json",
            response_json_schema=call.response_schema,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            http_options=types.HttpOptions(timeout=max(1, int(1000 * call.timeout_s))),
        )
        response = self._client.models.generate_content(
            model=call.model, contents=call.prompt, config=config
        )
        try:
            return json.loads(response.text)
        except (TypeError, json.JSONDecodeError) as error:
            raise ModelError(f"{call.key}: the model did not return JSON: {error}") from error


class FixtureModel:
    def __init__(self, root: Path) -> None:
        self._root = root

    def call(self, call: ModelCall) -> dict:
        path = self._root / f"{call.session_id}.json"
        recorded = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if call.key not in recorded:
            raise ModelError(f"no recorded response {call.key} for {call.session_id}")
        return recorded[call.key]
