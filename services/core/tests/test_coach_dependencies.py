"""The Coach calls its model with tools through LiteLLM, and LiteLLM imports `mcp` for that
without listing it as a requirement. When it was missing, every Coach run on Azure failed with
"APIConnectionError" (LiteLLM's name for any internal error) and the template plan was used."""

import importlib.util
import re
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"


def test_mcp_is_installed_for_litellm_tool_calls():
    assert importlib.util.find_spec("mcp") is not None


def test_mcp_is_pinned_in_the_core_requirements():
    lines = REQUIREMENTS.read_text().splitlines()
    assert any(re.fullmatch(r"mcp==\d+(\.\d+)*", line.strip()) for line in lines)


def test_a_litellm_call_with_tools_runs_without_a_network():
    """The call the Coach makes (tools included), with LiteLLM's own mock answer: no key and no
    connection. Without `mcp` this raised ModuleNotFoundError, which a real call reports as an
    APIConnectionError."""
    import litellm

    answer = litellm.completion(
        model="openai/gemini-3.1-flash-lite",
        api_base="http://127.0.0.1:9",  # nothing listens here: the mock never connects
        api_key="not-a-key",
        messages=[{"role": "user", "content": "Say hi."}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_report",
                    "description": "Get the report.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
        ],
        mock_response="hello",
        num_retries=0,
    )
    assert answer.choices[0].message.content == "hello"
