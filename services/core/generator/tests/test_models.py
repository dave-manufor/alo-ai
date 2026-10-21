"""The Vertex and recorded models behind the Writer and the Critic."""

from types import SimpleNamespace

import pytest
from services.core.generator.models import FixtureModel, ModelCall, ModelError, VertexModel

from .fakes import RECORDED

CALL = ModelCall(
    key="writer/1",
    session_id="sess_demo_001",
    model="gemini-2.5-flash",
    prompt="Write a story.",
    response_schema={"type": "object"},
    timeout_s=7.25,
    temperature=1.0,
)


class FakeClient:
    def __init__(self, text):
        self.text, self.seen = text, {}
        self.models = SimpleNamespace(generate_content=self.generate_content)

    def generate_content(self, *, model, contents, config):
        self.seen = {"model": model, "contents": contents, "config": config}
        return SimpleNamespace(text=self.text)


def test_vertex_asks_for_json_in_the_schema_within_the_timeout():
    client = FakeClient('{"title": "The Lost Goat"}')
    assert VertexModel(client).call(CALL) == {"title": "The Lost Goat"}
    config = client.seen["config"]
    assert client.seen["model"] == "gemini-2.5-flash"
    assert client.seen["contents"] == "Write a story."
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == {"type": "object"}
    assert config.temperature == 1.0
    assert config.thinking_config.thinking_budget == 0
    assert config.http_options.timeout == 7250


@pytest.mark.parametrize("text", [None, "not json"])
def test_vertex_text_that_is_not_json_is_refused(text):
    with pytest.raises(ModelError, match="did not return JSON"):
        VertexModel(FakeClient(text)).call(CALL)


def test_the_recorded_model_answers_by_session_and_key():
    assert FixtureModel(RECORDED).call(CALL)["title"] == "The Lost Goat"


@pytest.mark.parametrize(
    ("session_id", "key"), [("sess_demo_001", "writer/2"), ("sess_unknown", "writer/1")]
)
def test_a_missing_recording_is_refused(session_id, key):
    call = ModelCall(key, session_id, "m", "p", {}, 1.0)
    with pytest.raises(ModelError, match=f"no recorded response {key} for {session_id}"):
        FixtureModel(RECORDED).call(call)
