"""The models an evaluation run uses (PRD 13.4).

A live run calls the models of the chosen CLOUD, built exactly as Core builds them
(services/core/main.py), and spends from that cloud's budget: on gcp, Gemini on Vertex AI;
on azure, the role deployments through Azure OpenAI or, with LLM_BASE_URL, through an
OpenAI-compatible provider and its key (the Coach through ADK and LiteLLM, the Grader
directly). With recording on, it saves what the model did in the formats the recorded models
replay (RecordedModel, FixtureGradingModel), so CI repeats the run free and
deterministically. Recordings are kept per cloud (recorded/{cloud}/...), so one cloud's run
never replaces another's. Red-team cases put the attacker's message into the conversation
with InjectedModel.
"""

import json
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import aloai_env

from google.adk.models import BaseLlm, Gemini, LlmRequest, LlmResponse
from google.genai import types
from pydantic import Field
from services.core.coach.agent import COACH_MODEL, PROMPT_VERSION, RecordedModel
from services.core.grader.models import GradingModel, GradingTask, VertexGradingModel

ROOT = Path(__file__).resolve().parent
RECORDED = ROOT / "recorded"


def live_coach_model(settings: aloai_env.Config) -> BaseLlm:
    """The Reading Coach's live model, as Core builds it for this cloud."""
    if settings.cloud == "azure":
        from services.core.coach.azure import azure_coach_model

        return azure_coach_model(settings)("eval")
    return Gemini(
        model=COACH_MODEL,
        client_kwargs={
            "vertexai": True,
            "project": settings.project,
            "location": settings.location,
        },
    )


def live_grading_model(settings: aloai_env.Config) -> GradingModel:  # pragma: no cover
    """The Grader's live model, as Core builds it for this cloud (a real client)."""
    if settings.cloud == "azure":
        from aloai_azure import open_openai
        from services.core.grader.azure import azure_model

        return azure_model(open_openai(settings), settings)
    from google import genai

    return VertexGradingModel(
        genai.Client(vertexai=True, project=settings.project, location=settings.location)
    )


def recorded_dir(set_name: str) -> Path:
    """Where a set's recordings for this cloud (CLOUD, gcp by default) are kept."""
    return RECORDED / (os.environ.get("CLOUD") or "gcp") / set_name


def recording_path(set_name: str, case_id: str) -> Path:
    return recorded_dir(set_name) / f"{case_id}.json"


def recorded_model(set_name: str, case_id: str) -> RecordedModel:
    return RecordedModel.from_file(recording_path(set_name, case_id))


class RecordingModel(BaseLlm):
    """Passes each call to the live model and keeps its turns."""

    inner: BaseLlm
    turns: list[dict] = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        async for response in self.inner.generate_content_async(llm_request, stream):
            self.turns.append(recorded_turn(response))
            yield response

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        recording = {"model": self.model, "prompt_version": PROMPT_VERSION, "turns": self.turns}
        path.write_text(json.dumps(recording, indent=2, ensure_ascii=False) + "\n")


def recorded_turn(response: LlmResponse) -> dict:
    """A model turn as RecordedModel replays it: tool calls and visible text only."""
    parts = []
    for part in response.content.parts if response.content else []:
        if part.function_call:
            parts.append({"call": part.function_call.name, "args": part.function_call.args or {}})
        elif part.text and not part.thought:
            parts.append({"text": part.text})
    usage = response.usage_metadata
    return {"parts": parts, "tokens": (usage.total_token_count or 0) if usage else 0}


class InjectedModel(BaseLlm):
    """Adds the attacker's message after the run's request, on every call."""

    inner: BaseLlm
    message: str

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        attack = types.Content(role="user", parts=[types.Part(text=self.message)])
        llm_request.contents.insert(1, attack)
        async for response in self.inner.generate_content_async(llm_request, stream):
            yield response


class NoModel(BaseLlm):
    """For a case whose Coach must not reach the model at all."""

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        raise AssertionError("this case must not call the model")
        yield


class RecordingGrader:
    """Passes each grading call to the live model and keeps its outputs by call key."""

    def __init__(self, inner: GradingModel) -> None:
        self.inner = inner
        self.outputs: dict[str, dict] = {}

    def grade(self, task: GradingTask) -> dict:
        self.outputs[task.key] = self.inner.grade(task)
        return self.outputs[task.key]

    def save(self, directory: Path, session_id: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{session_id}.json"
        path.write_text(json.dumps(self.outputs, indent=2, ensure_ascii=False) + "\n")
