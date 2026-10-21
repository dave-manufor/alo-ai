"""The generator's model call and clip URIs on Azure, against a fake client: nothing here
reaches Azure. This does not replace the Writer + Critic evaluation set (PRD 13.4)."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from services.core.generator import clips
from services.core.generator.azure import AzureModel
from services.core.generator.models import ModelCall, ModelError, UpstreamErrors


class ChatFake:
    def __init__(self, content='{"title": "x"}', choices=None):
        self.calls = []
        self._response = SimpleNamespace(
            choices=choices
            if choices is not None
            else [SimpleNamespace(message=SimpleNamespace(content=content))]
        )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def call(**changes):
    base = ModelCall(
        key="writer/1",
        session_id="sess",
        model="gemini-2.5-flash",
        prompt="Write a story.",
        response_schema={
            "$schema": "x",
            "type": "object",
            "properties": {"title": {"type": "string"}},
        },
        timeout_s=12.0,
        temperature=1.0,
    )
    return replace(base, **changes)


def test_the_writer_call_goes_to_the_generator_deployment_in_its_schema_and_time():
    client = ChatFake()
    assert AzureModel(client, "aloai-generator").call(call()) == {"title": "x"}
    [sent] = client.calls
    assert sent["model"] == "aloai-generator"
    assert sent["messages"] == [{"role": "user", "content": "Write a story."}]
    assert (sent["temperature"], sent["timeout"]) == (1.0, 12.0)
    schema = sent["response_format"]["json_schema"]
    assert sent["response_format"]["type"] == "json_schema"
    assert schema["strict"] is False
    assert "$schema" not in schema["schema"]


@pytest.mark.parametrize("key", ["writer/1", "critic_b/2", "x" * 100])
def test_the_schema_name_is_one_openai_accepts(key):
    client = ChatFake()
    AzureModel(client, "d").call(call(key=key))
    name = client.calls[0]["response_format"]["json_schema"]["name"]
    assert name and len(name) <= 64 and all(c.isalnum() or c in "_-" for c in name)


@pytest.mark.parametrize(
    "client",
    [ChatFake(content="not json"), ChatFake(content=None), ChatFake(choices=[])],
    ids=["not json", "no content", "no choices"],
)
def test_an_answer_that_is_not_json_is_a_model_error(client):
    with pytest.raises(ModelError, match="writer/1"):
        AzureModel(client, "d").call(call())


def test_azure_failures_are_upstream_errors_to_retry():
    import openai
    from azure.core.exceptions import ServiceRequestError

    request = SimpleNamespace(method="POST", url="https://x")
    assert issubclass(openai.APITimeoutError, UpstreamErrors)
    assert isinstance(openai.APIConnectionError(request=request), UpstreamErrors)
    assert isinstance(ServiceRequestError("down"), UpstreamErrors)


def test_clip_uris_name_the_scheme_of_the_cloud():
    azure = clips.word_clip_uri("clips", "vp_azure_v1", "v1", "az")
    google = clips.word_clip_uri("aloai-dev-clips", "vp_google_v1", "v1")
    assert azure("rain", None) == "az://clips/vp_azure_v1/v1/words/rain.mp3"
    assert google("rain", None) == "gs://aloai-dev-clips/vp_google_v1/v1/words/rain.mp3"
    assert json.dumps(azure("tunde", "ˈtundɛ")).count("az://") == 1
