# ADR 0001: Azure as a second cloud, chosen by `CLOUD`

**Status:** accepted (2026-10-21)
**Deciders:** W2 (David), with W1 and W3 informed through the PR
**Spec:** PRD section 0 (changelog), 3, 14.5, 15

## Context

The PRD builds Alo.ai on Google Cloud with a $400 budget. No GCP credits could be secured, so Cloud Run, Vertex AI, Chirp, Cloud Text-to-Speech, Cloud Storage and Pub/Sub are not available to us. We have **US$150 of Azure credit**.

Today each service builds Google clients directly (`services/core/main.py`, `services/reading_scorer/main.py`, `services/session_agent/livekit_worker.py`). The domain code mostly sits behind small Protocols that already have a fixture or memory fake: `Store`, `Publisher`, `Bucket`, `AudioSource`, `GradingModel`, `Transcriber`, `Embedder`, `Speaker`, the generator's `Model` and the `Tagger`.

## Decision

1. **One server setting, `CLOUD=gcp|azure`** (default `gcp`), set by Terraform. The browser never sets it (hard rule 8). `AI_MODE=fixtures` stays the default for laptops and CI and needs neither cloud.
2. **Adapters, not rewrites.** Add Azure classes beside the Google ones behind the same Protocols. Import the Google and Azure SDKs inside the factories, so fixture mode and the other cloud need neither.
3. **Everything on Azure when `CLOUD=azure`:** Cosmos DB instead of Firestore, Service Bus instead of Pub/Sub, Blob Storage instead of Cloud Storage, Entra External ID instead of Firebase Auth.
4. **`cache_first` only on Azure.** Gemini Live is not built yet and Azure realtime voice would use the credit quickly. "That word is X." is a clip in either cloud (hard rule 8).
5. **Contracts widen, and their versions are bumped (hard rule 4).** Blob references are `gs://` or `az://`; `book.embedding_model` is either pinned model. Existing values stay valid, but each affected schema's `schema_version` goes up anyway: `book` 2, `passage` 4, `plan` 2, the session turn record 3, and the events `phase1.recorded` 2 and `session.done` 3. Fixtures, producers (`aloai_events.SCHEMA_VERSIONS`, the Session Agent's `events.py` and `session_store.py`, the Coach's `plan.py`) and tests move with them.
6. **The GCP adapters stay and keep working,** so we can switch back if credits arrive.

## Service map

| Google Cloud (PRD) | Azure | Notes |
|---|---|---|
| Cloud Run services and job | Container Apps (Consumption) and a Container Apps Job | The Session Agent keeps min 1 replica |
| Artifact Registry | Container Registry (Basic) | Pulled with managed identity |
| Cloud Storage | Blob Storage: `audio` (90-day lifecycle), `clips` (public read), `books` | `az://{container}/{name}` |
| Firestore and its vector index | Cosmos DB for NoSQL (free tier) with a vector path on `books` | Partition key is the top-level document path |
| Pub/Sub push, 600 s deadline | Service Bus Basic, one queue per consumer | Not Event Grid push: its 30 s webhook limit is shorter than Pro grading. Dead-letter after 5 deliveries |
| Secret Manager | Key Vault | Values set outside Terraform |
| Google ID tokens between services | Managed identity tokens checked against Entra keys | Core and Scorer use internal ingress |
| Gemini 2.5 Pro and Flash | Azure OpenAI deployments named in env | Confirm regional availability first |
| `text-embedding-005` | `text-embedding-3-small` at 768 dimensions | Re-embed the catalogue |
| Chirp 3 (batch, sync, streaming) | Azure AI Speech, and its LiveKit streaming plugin | Check per-word confidence first |
| Gemini verbatim audio transcript | Azure OpenAI `gpt-4o-transcribe` | Audio sent as bytes, not a URI |
| Cloud Text-to-Speech Chirp 3 HD | Azure neural voices with SSML `phoneme` | New `voice_profile_id`, so both clip sets can coexist |
| Firebase Auth and Hosting | Entra External ID and Static Web Apps | The web app has no Firebase code yet |
| `europe-west1` | `swedencentral` | Still EU (hard rule 9) |

## Consequences

- **Budget** (estimate, recheck prices): about $35 to $50 of the $150 for the sprint. Alerts at $50, $100 and $130.
- **Evaluation reruns.** Every model change reruns its set and pastes the result in the PR (hard rule 6). Azure models will not match the recorded Gemini answers, so each set is recorded again for Azure.
- **Day-1 check on Azure Speech,** in the spirit of PRD 5.2: per-word confidence, the locale (`en-NG` or `en-GB`), and verbatim text on misreads. If confidence is missing, the existing "every word is 0.0" path applies and any change to the UNCERTAIN rule goes through W3 (hard rule 5).
- **Terraform.** `infra/azure/` is a second flat root next to the GCP one (hard rule 7 applies to it). Secret values stay out of state.
- **Ownership.** Most of the work sits in W1 (Terraform, auth, hosting) and W3 (shared library, Scorer, Grader, Coach) areas. Each PR names its owner.

## Order of work

1. Contracts and docs (this PR).
2. Shared library seams: `CLOUD` in `aloai_env`, `Blobs`, `CosmosStore`, `ServiceBusPublisher`, service-to-service tokens, with the existing Store and Publisher contract tests run over every backend.
3. Event handling split into one `handle(event)` used by the Pub/Sub push route and the Service Bus pump.
4. AI adapters, split by owner, each with its evaluation result.
5. `infra/azure/` Terraform.
6. Web sign-in and hosting.
7. Seed clips, the book catalogue and bank passages.
