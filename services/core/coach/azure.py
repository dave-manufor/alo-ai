"""The Reading Coach's Azure counterparts to Gemini and Chirp text-to-speech (CLOUD=azure;
the Google ones are in agent.py and clients.py).

azure_coach_model gives ADK a model on an Azure OpenAI deployment (role "coach") through
LiteLLM, which speaks the OpenAI v1 API Azure OpenAI offers. ADK still runs the agent, so the
tools, `authorize()` and the guardrail are unchanged. The credential is an access token that
lasts about an hour, so the model is built for each run, not kept. AzureSpeaker is Auntie
Kemi's voice (PRD 4.6) from Azure AI Speech, saved beside the session's audio.
"""

from collections.abc import Callable
from dataclasses import dataclass

from aloai_azure import bearer_token, build_ssml, deployment, openai_base_url
from aloai_blobs import Blobs, blob_uri
from aloai_env import Config
from google.adk.models import BaseLlm
from google.adk.models.lite_llm import LiteLlm

from .clients import SPEAKING_RATE


def azure_coach_model(
    config: Config, token: Callable[[Config], str] = bearer_token
) -> Callable[[str], BaseLlm]:
    name = deployment(config, "coach")
    base_url = openai_base_url(config)

    def model_for(session_id: str) -> BaseLlm:
        return LiteLlm(model=f"openai/{name}", api_base=base_url, api_key=token(config))

    return model_for


@dataclass(frozen=True)
class AzureSpeaker:
    blobs: Blobs
    synthesize: Callable[[str], bytes]  # SSML -> MP3 (aloai_azure.synthesize)
    container: str
    voice: str  # e.g. en-US-JennyNeural

    def speak(self, text: str, session_id: str) -> str | None:
        locale = "-".join(self.voice.split("-")[:2])
        rate = f"{round((SPEAKING_RATE - 1) * 100)}%"
        audio = self.synthesize(build_ssml(text, voice=self.voice, locale=locale, rate=rate))
        uri = blob_uri("azure", self.container, f"{session_id}/summary/summary.mp3")
        self.blobs.write(uri, audio, "audio/mpeg")
        return uri
