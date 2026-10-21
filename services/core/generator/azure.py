"""The Story Writer's and the Critic's model calls on Azure (CLOUD=azure; the Google one is
VertexModel in models.py).

AzureModel asks an Azure OpenAI deployment (the role "generator") for a JSON answer in the
call's response schema, at the call's temperature and within its time limit. The schema is
sent as a response format that is not strict, because it holds more than strict structured
output takes; the pipeline checks every answer against it anyway. The model name a call
carries (FLASH) is the Gemini one: here it only means "the generator's model".
"""

import json
import re

from .models import ModelCall, ModelError

_NAME = re.compile(r"[^A-Za-z0-9_-]")


class AzureModel:
    def __init__(self, client, deployment: str) -> None:
        """client is an openai.OpenAI on the Azure OpenAI v1 API."""
        self._client = client
        self._deployment = deployment

    def call(self, call: ModelCall) -> dict:
        schema = {k: v for k, v in call.response_schema.items() if k not in ("$schema", "$id")}
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[{"role": "user", "content": call.prompt}],
            temperature=call.temperature,
            response_format={
                "type": "json_schema",
                # The name must be letters, digits, "_" and "-": a call key is "writer/1".
                "json_schema": {
                    "name": _NAME.sub("_", call.key)[:64],
                    "schema": schema,
                    "strict": False,
                },
            },
            timeout=call.timeout_s,
        )
        choices = response.choices
        try:
            return json.loads(choices[0].message.content if choices else None)
        except (TypeError, json.JSONDecodeError) as error:
            raise ModelError(f"{call.key}: the model did not return JSON: {error}") from error
