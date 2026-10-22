"""Settings every Alo.ai service reads once from the environment.

CLOUD says which cloud the services build their clients for: "gcp" (Firestore, Pub/Sub,
Cloud Storage, Vertex AI) or "azure" (Cosmos DB, Service Bus, Blob Storage, Azure OpenAI).
Terraform sets it; the browser never does. Each cloud's clients are imported only when
that cloud is chosen (aloai_store.open_store, aloai_blobs.open_blobs,
aloai_events.open_publisher), so recorded-AI runs and the other cloud need neither SDK.

Local shortcuts must never run in a hosted service. Cloud Run sets K_SERVICE in a service
and CLOUD_RUN_JOB in a job; Container Apps sets CONTAINER_APP_NAME and
CONTAINER_APP_JOB_NAME. There, ALO_ENV=local (emulators) is refused, and so are the
recorded AI responses (AI_MODE=fixtures, the default), so a deployment that forgets
AI_MODE=live stops at start instead of replaying recordings. On Azure the connection
strings and keys (AZURE_*_CONNECTION_STRING, AZURE_COSMOS_KEY, AZURE_OPENAI_API_KEY,
AZURE_SPEECH_KEY) are refused too: hosted services use their managed identity. A Cloud Run service also needs
PUSH_SERVICE_ACCOUNT, the identity Pub/Sub pushes with, so its push route can turn away any
other caller (aloai_events.pushed_by). PUSH_AUDIENCE, the subscription's token audience, is
optional: set, it also refuses a token minted for another endpoint. Azure services take
events from Service Bus queues instead of pushes, so they need neither.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass

AI_MODES = ("fixtures", "live")
CLOUDS = ("gcp", "azure")
CLOUD_RUN_ENV = ("K_SERVICE", "CLOUD_RUN_JOB")
CONTAINER_APPS_ENV = ("CONTAINER_APP_NAME", "CONTAINER_APP_JOB_NAME")
AZURE_LOCAL_ONLY = (
    "AZURE_STORAGE_CONNECTION_STRING",
    "AZURE_COSMOS_KEY",
    "AZURE_SERVICEBUS_CONNECTION_STRING",
    "AZURE_OPENAI_API_KEY",
    "AZURE_SPEECH_KEY",
)
DEFAULT_LOCATION = {"gcp": "europe-west1", "azure": "swedencentral"}


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    alo_env: str
    ai_mode: str
    project: str
    location: str
    push_service_account: str | None = None
    push_audience: str | None = None
    cloud: str = "gcp"
    hosted: bool = False
    # Azure only. The endpoints name the resources; the services reach them with their
    # managed identity. The connection string and key are for emulators and are refused
    # when hosted.
    cosmos_endpoint: str | None = None
    cosmos_database: str = "aloai"
    servicebus_namespace: str | None = None
    storage_account: str | None = None
    storage_connection_string: str | None = None
    cosmos_key: str | None = None
    servicebus_connection_string: str | None = None
    # Event type -> the queues it goes to (infra/events.json, written into the app's env).
    event_routes: Mapping[str, tuple[str, ...]] | None = None
    # The queue this service takes its events from (Azure): core-events, scorer-events.
    event_queue: str | None = None
    # Azure AI. Deployments name the Azure OpenAI deployment for each role (grader, quick,
    # coach, embedding, transcribe, ...); the services reach OpenAI and Speech with their
    # managed identity. The keys are for local runs and are refused when hosted.
    openai_endpoint: str | None = None
    openai_key: str | None = None
    openai_deployments: Mapping[str, str] | None = None
    # An OpenAI-compatible provider outside Azure OpenAI (LLM_BASE_URL, for example Mistral),
    # used for the chat and transcription roles in place of the Azure OpenAI endpoint. Its API
    # key is a secret (Key Vault) and is required with the URL, so the managed identity's
    # token is never sent to it. Deployments still name the model for each role.
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    speech_region: str | None = None
    speech_resource_id: str | None = None
    speech_key: str | None = None
    speech_locale: str = "en-GB"  # PRD 5.2: the day-1 transcript check confirms or changes it


def load(env: Mapping[str, str], *, receives_pushes: bool = True) -> Config:
    """The settings. A Cloud Run service that receives Pub/Sub pushes (Core, the Scorer) must name
    the push identity; one that does not (receives_pushes=False, the Session Agent) need not."""
    cloud = env.get("CLOUD", "gcp")
    if cloud not in CLOUDS:
        raise ConfigError(f"CLOUD={cloud!r} is not one of {sorted(CLOUDS)}")
    on_cloud_run = any(env.get(name) for name in CLOUD_RUN_ENV)
    on_container_apps = any(env.get(name) for name in CONTAINER_APPS_ENV)
    hosted = on_cloud_run or on_container_apps
    where = "Cloud Run" if on_cloud_run else "Container Apps"
    alo_env = env.get("ALO_ENV", "")
    if alo_env == "local" and hosted:
        raise ConfigError(f"ALO_ENV=local is not allowed on {where}")
    ai_mode = env.get("AI_MODE", "fixtures")
    if ai_mode not in AI_MODES:
        raise ConfigError(f"AI_MODE={ai_mode!r} is not one of {sorted(AI_MODES)}")
    if ai_mode == "fixtures" and hosted:
        raise ConfigError(f"recorded AI responses (AI_MODE=fixtures) are not allowed on {where}")
    push_service_account = env.get("PUSH_SERVICE_ACCOUNT") or None
    if receives_pushes and env.get("K_SERVICE") and push_service_account is None:
        raise ConfigError("PUSH_SERVICE_ACCOUNT must be set on a Cloud Run service")
    llm_base_url = env.get("LLM_BASE_URL") or None
    llm_api_key = env.get("LLM_API_KEY") or None
    if llm_base_url and not llm_api_key:
        raise ConfigError("LLM_API_KEY must be set with LLM_BASE_URL")
    if llm_base_url and hosted and not llm_base_url.startswith("https://"):
        raise ConfigError(f"LLM_BASE_URL must be an https:// address on {where}")
    if hosted:
        local_only = [name for name in AZURE_LOCAL_ONLY if env.get(name)]
        if local_only:
            raise ConfigError(
                f"{', '.join(local_only)} is not allowed on {where}: use the managed identity"
            )
    return Config(
        alo_env=alo_env,
        ai_mode=ai_mode,
        project=env.get("GOOGLE_CLOUD_PROJECT", "aloai-dev"),
        location=env.get("GOOGLE_CLOUD_LOCATION") or DEFAULT_LOCATION[cloud],
        push_service_account=push_service_account,
        push_audience=env.get("PUSH_AUDIENCE") or None,
        cloud=cloud,
        hosted=hosted,
        cosmos_endpoint=env.get("AZURE_COSMOS_ENDPOINT") or None,
        cosmos_database=env.get("AZURE_COSMOS_DATABASE") or "aloai",
        servicebus_namespace=env.get("AZURE_SERVICEBUS_NAMESPACE") or None,
        storage_account=env.get("AZURE_STORAGE_ACCOUNT") or None,
        storage_connection_string=env.get("AZURE_STORAGE_CONNECTION_STRING") or None,
        cosmos_key=env.get("AZURE_COSMOS_KEY") or None,
        servicebus_connection_string=env.get("AZURE_SERVICEBUS_CONNECTION_STRING") or None,
        event_routes=_routes(env.get("EVENT_ROUTES")),
        event_queue=env.get("EVENT_QUEUE") or None,
        openai_endpoint=env.get("AZURE_OPENAI_ENDPOINT") or None,
        openai_key=env.get("AZURE_OPENAI_API_KEY") or None,
        openai_deployments=_deployments(env.get("AZURE_OPENAI_DEPLOYMENTS")),
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        speech_region=env.get("AZURE_SPEECH_REGION") or None,
        speech_resource_id=env.get("AZURE_SPEECH_RESOURCE_ID") or None,
        speech_key=env.get("AZURE_SPEECH_KEY") or None,
        speech_locale=env.get("AZURE_SPEECH_LOCALE") or "en-GB",
    )


def require_setting(value: str | None, name: str) -> str:
    """A setting a client needs, or a ConfigError that names it."""
    if not value:
        raise ConfigError(f"{name} must be set")
    return value


def _deployments(raw: str | None) -> Mapping[str, str] | None:
    """AZURE_OPENAI_DEPLOYMENTS is JSON: {"grader": "gpt-4.1", "quick": "gpt-4.1-mini", ...}."""
    if not raw:
        return None
    try:
        found = json.loads(raw)
        if not isinstance(found, dict) or not all(
            isinstance(role, str) and isinstance(name, str) and name for role, name in found.items()
        ):
            raise ValueError(raw)
    except ValueError as error:
        raise ConfigError(
            "AZURE_OPENAI_DEPLOYMENTS must be JSON: {role: deployment name}"
        ) from error
    return found


def _routes(raw: str | None) -> Mapping[str, tuple[str, ...]] | None:
    """EVENT_ROUTES is JSON: {"core-events": ["session.done", ...], ...} (queue -> types)."""
    if not raw:
        return None
    try:
        queues = json.loads(raw)
        routes: dict[str, list[str]] = {}
        for queue, types in queues.items():
            for event_type in types:
                routes.setdefault(event_type, []).append(queue)
    except (ValueError, AttributeError, TypeError) as error:
        raise ConfigError("EVENT_ROUTES must be JSON: {queue: [event types]}") from error
    return {event_type: tuple(queues) for event_type, queues in routes.items()}
