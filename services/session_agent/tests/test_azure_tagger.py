"""The interest tagger and the story requester on Azure (CLOUD=azure). A fake client: nothing
here reaches Azure. This does not replace the tagger evaluation set (PRD 13.4)."""

import asyncio
import json
from types import SimpleNamespace

import aloai_env
import pytest
from services.session_agent import config, generation, livekit_worker
from services.session_agent.machine.profiles import DEMO

from .test_worker_parts import BANK


class ChatFake:
    def __init__(self, content=None, choices=None):
        self.calls = []
        answer = (
            content if content is not None else json.dumps({"tags": ["animals"], "details": ["goat"]})
        )
        self._response = SimpleNamespace(
            choices=choices
            if choices is not None
            else [SimpleNamespace(message=SimpleNamespace(content=answer))]
        )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def tag(client, answer="I like goats"):
    return asyncio.run(generation.AzureTagger(client, "aloai-tagger").tag(answer))


def test_the_answer_is_tagged_by_the_tagger_deployment_in_the_same_schema_and_time():
    client = ChatFake()
    assert tag(client) == generation.Interest(("animals",), ("goat",))
    [sent] = client.calls
    assert sent["model"] == "aloai-tagger"
    assert (sent["temperature"], sent["timeout"]) == (0, generation.TAGGER_TIMEOUT_S)
    [message] = sent["messages"]
    assert message["content"].startswith(generation.TAGGER_INSTRUCTIONS)
    assert message["content"].endswith("<child>I like goats</child>")
    schema = sent["response_format"]["json_schema"]
    assert (schema["schema"], schema["strict"]) == (generation.TAGGER_SCHEMA, False)


def test_only_known_tags_and_a_safe_detail_survive():
    client = ChatFake(json.dumps({"tags": ["animals", "wizards", "animals"], "details": ["Tunde!"]}))
    assert tag(client) == generation.Interest(("animals",), ())


@pytest.mark.parametrize(
    "client",
    [ChatFake(content="not json"), ChatFake(choices=[]), ChatFake(content="[1]")],
    ids=["not json", "no choices", "not an object"],
)
def test_an_answer_that_is_unusable_is_no_interest(client):
    assert tag(client) == generation.NO_INTEREST


def test_the_azure_tagger_is_chosen_on_azure_with_the_tagger_deployment(monkeypatch):
    made = []
    monkeypatch.setattr(
        livekit_worker, "open_openai_async", lambda shared: made.append(shared) or "client"
    )
    shared = aloai_env.load(
        {
            "ALO_ENV": "local",
            "CLOUD": "azure",
            "AZURE_OPENAI_DEPLOYMENTS": '{"tagger": "aloai-tagger"}',
        },
        receives_pushes=False,
    )
    tagger = livekit_worker._tagger(
        config.worker_settings({"CLOUD": "azure", "CLIPS_BASE_URL": "x"}), shared
    )
    assert isinstance(tagger, generation.AzureTagger)
    assert (tagger._client, tagger._deployment) == ("client", "aloai-tagger")
    assert made == [shared]


def test_the_azure_tagger_needs_a_tagger_deployment(monkeypatch):
    monkeypatch.setattr(livekit_worker, "open_openai_async", lambda shared: "client")
    shared = aloai_env.load({"ALO_ENV": "local", "CLOUD": "azure"}, receives_pushes=False)
    with pytest.raises(aloai_env.ConfigError, match="'tagger'"):
        livekit_worker._tagger(
            config.worker_settings({"CLOUD": "azure", "CLIPS_BASE_URL": "x"}), shared
        )


def test_the_gcp_tagger_is_still_gemini_on_vertex(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        livekit_worker.genai, "Client", lambda **kwargs: seen.update(kwargs) or "vertex"
    )
    shared = aloai_env.load({"ALO_ENV": "local"}, receives_pushes=False)
    tagger = livekit_worker._tagger(config.worker_settings({}), shared)
    assert isinstance(tagger, generation.VertexTagger)
    assert seen["vertexai"] is True and seen["location"] == "europe-west1"


def test_a_live_azure_session_with_the_generator_on_gets_a_story_requester(monkeypatch):
    monkeypatch.setattr(livekit_worker, "open_openai_async", lambda shared: "client")
    cfg = config.Config("", "live", "cache_first", "demo", True)
    settings = config.worker_settings({"CLOUD": "azure", "CLIPS_BASE_URL": "x"})
    shared = aloai_env.load(
        {"ALO_ENV": "local", "CLOUD": "azure", "AZURE_OPENAI_DEPLOYMENTS": '{"tagger": "t"}'},
        receives_pushes=False,
    )
    start = SimpleNamespace(ctx=SimpleNamespace(session_id="sess_1"), child_id="child_1")
    requester = livekit_worker._story_requester(settings, cfg, start, DEMO, BANK, None, shared)
    assert isinstance(requester.tagger, generation.AzureTagger)
