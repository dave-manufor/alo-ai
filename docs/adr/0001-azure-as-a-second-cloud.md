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
2. Shared library seams (`libs/aloai`, W3's area). Built:
   - `aloai_env`: `CLOUD`, a `hosted` check that sees Container Apps as well as Cloud Run (so the hard rule 8 guards hold on Azure), the Azure resource settings, and `EVENT_ROUTES`.
   - `aloai_blobs`: `Blobs` with `MemoryBlobs`, `GcsBlobs` and `AzureBlobs`, and one `BlobNotFound` on every backend.
   - `aloai_store`: `CosmosStore` beside `FirestoreStore`. Items are `{id, pk, col, d}`; `merge` retries under the etag, so it keeps Firestore's merge behaviour.
   - `aloai_events`: `ServiceBusPublisher`, `QueuePump` and `pump_once`. A handler that returns completes the message and one that raises abandons it, so Service Bus redelivers it and then dead-letters it, as Pub/Sub does. `infra/events.json` is the queue-to-event-type table that Terraform turns into queues and into `EVENT_ROUTES`.
   - `aloai_service_auth` (not `aloai_authz`, which is agent authorization): `google_caller` (what `pushed_by` now wraps), `entra_caller`, and `service_token`.
   - One store contract and one blob contract run against every backend.
   - Each cloud's SDK is imported only inside its own classes, and `libs/aloai/pyproject.toml` has the extras `[gcp]` and `[azure]`.
   - Cosmos DB limits to plan for: one container `docs` (partition key `/pk`) and one `books` with a vector path.
3. Event handling split into one `handle(event)` used by the Pub/Sub push route and the Service Bus pump. Built:
   - `event_handler` in Core (`services/core/api.py`) and in the Reading Scorer (`services/reading_scorer/api.py`). It returns once an event is done with (handled, ignored, or parked because it can never succeed) and raises for anything else. The routes keep their signatures and call it.
   - `build_app` in each `main.py`: on `gcp` it mounts the push route; on `azure` it does not (nothing on Azure signs a push, so an unsigned route would let any app in the environment post a `session.done`) and instead pumps the service's own queue (`EVENT_QUEUE`) through `aloai_events.pump_lifespan`.
   - Both `main.py` files build their store and publisher with `open_store` and `open_publisher`, and the Scorer reads audio through `BlobAudio` over any `Blobs`. A recording that is not in storage is now a `BlobNotFound` (a `LookupError`), so the Scorer parks it, as it parks a missing document; before, a missing Cloud Storage object was retried and then dead-lettered.
   - Not built yet, so Core and the Scorer name it and refuse to start on azure: book search (Core) and the live AI clients, speech and voice (both). They come with step 4.
   - Core calls the Account service with `aloai_service_auth.service_token`, so it works on either cloud.
4. AI adapters, split by owner, each with its evaluation result. **W3 part built, evaluations not run:**
   - `libs/aloai/aloai_azure.py`: the deployment for a role, the OpenAI v1 client (`{endpoint}/openai/v1/`, so the deployment name is the `model` and no api-version is set), the audio Speech takes, what a recognition returns, the SSML for a voice (with an IPA `phoneme` for a name), and the two Speech SDK calls.
   - Core: `AzureGradingModel` (JSON-schema response format, not strict, checked by `grade()` afterwards; the quick and grader deployments by role), `AzureSpeechTranscriber`, `AzureEmbedder` (`text-embedding-3-small` asked for 768 dimensions), `CosmosBookSearch` (`VectorDistance`, nearest first, held books and other levels left out), and the Coach's `azure_coach_model` (ADK through LiteLLM, a fresh token for each run) and `AzureSpeaker`.
   - Reading Scorer: `AzureSpeechReading` (the passage's names as phrase hints) and `OpenAIReading` (a transcription deployment, verbatim prompt, temperature 0).
   - The report's `versions` now name the models actually called, so an Azure report says `azure-openai/<deployment>` and `azure-speech/<locale>`, not the Gemini and Chirp names.
   - `UpstreamErrors` also counts OpenAI and azure-core errors, so the quick endpoint still answers 503 with `retryable: true`.
   - **Not run, so not claimed:** the evaluation sets (hard rule 6), the day-1 Azure Speech check, and every call to a real Azure service. Unit tests use fake clients. The Speech SDK calls (`recognize_words`, `synthesize`) and the parse of Speech's detailed JSON follow the SDK's documented shapes and are the least certain parts: check that Speech returns a confidence for each word (without one, every word is left unmarked), that the transcription model keeps a child's mistakes instead of correcting them to the passage, and the 2.5 s quick-grade timeout on the quick deployment.
   - **W2 part built (Session Agent, clips), also not run against Azure:**
     - The worker takes its storage, documents and events from the shared clients (`open_blobs`, `open_store`, `open_publisher`), chosen by `CLOUD`. `cloud.py` is now one `BlobBucket` over any `Blobs`; the Google-only copies are gone.
     - Turn audio and clip URIs follow the cloud (`az://` on Azure) through a `scheme` on `AudioLog` and `ClipStore`.
     - Streaming STT is `livekit.plugins.azure.STT` on Azure, with the key locally or the managed identity's token (`aad#{resource id}#{token}`) when hosted; Chirp 3 stays on GCP.
     - The call to Core gets a token from the cloud it runs on (`service_token`). On Azure the audience is `CORE_AUDIENCE` (an app ID URI), not Core's URL.
     - The Session Agent now refuses `ALO_ENV=local` on Container Apps too, and `aloai_env.load(..., receives_pushes=False)` lets it start on Cloud Run without a push identity.
     - Clips: `clips/azure.py` makes the `synthesize(text, ipa)` that `seed_words` takes from an Azure voice, with an IPA `phoneme` for names. Use a new `VOICE_PROFILE_ID` for an Azure voice. There is still no seed command (it was not started), so nothing makes clips yet.
     - The image now ships `libs/aloai` and `schemas/` (as the Scorer's does) and the Azure pins. Not built: no Docker build was run.
   - **Generator and tagger (W2), built after #28 to #31 reached `main`, not evaluated:**
     - `services/core/generator/azure.py`: `AzureModel` for the Writer and the Critic (the "generator" deployment; JSON-schema response format, not strict, checked by the pipeline afterwards). `UpstreamErrors` also counts OpenAI and azure-core errors, so the endpoint still answers retryable.
     - `services/session_agent/generation.py`: `AzureTagger` (the "tagger" deployment), async, with the same instructions, schema and answer check as `VertexTagger`; `open_openai_async` in `aloai_azure`.
     - Generated passages name `az://` word clips on Azure (`Generator.scheme`, `word_clip_uri`).
     - `infra/azure`: `generator_on` (default false, written into the Session Agent and Core as `GENERATOR_ON`), the `generator` and `tagger` deployments, and the Session Agent's OpenAI role and settings.
     - **Keep `GENERATOR_ON` false.** The Writer + Critic and tagger evaluation sets have not run on Azure (hard rule 6), and no clip maker (G5) exists on any cloud, so a generated story's words have no clips. The seed command covers the bank only. Core also needs spaCy and `en_core_web_sm` in its image, and there is no Core Dockerfile.
5. `infra/azure/` Terraform.
6. Web sign-in and hosting. **Built, not run against Azure:**
   - `apps/web/src/auth`: Entra External ID through MSAL (`@azure/msal-browser`, loaded only in a real build), as a public client with PKCE and its session in `sessionStorage`. "Continue with Google" and "Continue with email" (an emailed code) both go to Entra's hosted page, which verifies the guardian; nobody is signed in by the click itself. The build's mode comes from `VITE_ENTRA_*`, never from the browser, and without them the sample sign-in stays.
   - In a real build the account (children, consents) is kept in memory for the tab, not in `localStorage`, because a child's name must not stay on a shared phone and there is no Account service to hold it yet. The real build cannot be used for real families until that exists.
   - `sign_in_method` gains `email_code`. There is no consent schema in `schemas/` yet; W1 adds the value when it defines one with the Account service.
   - Hosting: `azurerm_static_web_app` (Free, West Europe), `public/staticwebapp.config.json` (SPA fallback, caching, a Content-Security-Policy, the microphone permission), and a manual-dispatch deploy workflow that reads the deployment token at run time. The Entra tenant, app registration and Google provider are set up by hand (`apps/web/README.md`).
   - Not verified: the Static Web Apps emulator would not start, so the policy and routing were not run, and the deploy workflow has not run.
7. Seed clips, the book catalogue and bank passages. **Built for what exists; the catalogue itself does not:**
   - `python -m services.session_agent.seed` makes every clip a session can play (the 15 fixed prompts, each READ passage's questions, each LISTEN passage's story and item prompts, and "That word is X." for every word of every READ passage, with an IPA for names), then writes the bank passages. Clips are written only if absent, so it can be run again, and a new voice is a new `VOICE_PROFILE_ID`. It checks itself against the real `ClipCatalog`: after a run, every clip URL a demo or a standard session asks for exists.
   - A stored passage's clip URIs now name this cloud's store (`az://clips/vp_azure_v1/...`). The fixtures in `fixtures/contracts` named the Google dev bucket, and in a layout (`listening/...`) that did not match the one the Session Agent actually reads.
   - With `AI_MODE=live` and `CLOUD=azure` the voice is `TTS_VOICE` (an Azure Speech call per clip, 16 at a time). With `AI_MODE=fixtures` the clips are silent placeholders for a laptop. There is no Google voice: Cloud Text-to-Speech clips were never built, so `CLOUD=gcp` live is refused.
   - `services/core/books/embedding.py` fixes the one text a book is embedded from (`book_text`: description, then its topic tags written as interests are), and `python -m services.core.books.reembed` embeds again every book still on another model, checking each new vector (768 numbers, and the whole document against `book.schema.json`) before it writes. **There is no catalogue to move.** The book ingestion job (PRD 9.1) was never built and no real, open-licence books exist in the repository, so nothing here was run on real books and none are invented. The ingestion job must embed with `book_text` so the catalogue never holds two kinds of text.
   - Two manual jobs in `infra/azure`: `seed` (the Session Agent's identity and image) and `book_ingest` (the Core image, now running the re-embed command rather than its web server).
   - Not run against Azure. There is no Core Dockerfile yet, so the `book_ingest` job has no image to run.

## Exception to the EU-only rule: the web app's Static Web Apps region (2026-10-22)

**What.** `web_location` (the region of the `azurerm_static_web_app` resource) is `westus2` instead of `westeurope`. Everything else stays in `swedencentral`: Cosmos DB, Storage, Service Bus, Key Vault, the Container Apps, Azure OpenAI and Azure AI Speech.

**Why.** `westeurope` refused the resource on the first apply: "The selected region is currently not accepting new customers" (`RequestDisallowedByAzure`). Static Web Apps is offered in few regions, and `westeurope` was the only EU one.

**Scope of the exception.** The Static Web Apps resource holds the site configuration and serves the built app from Azure's edge network. The app contains no child data: sign-in, children, consents and reports go to the Account API in the EU. The app's `connect-src` policy (`staticwebapp.config.json`) allows the site itself, Entra (`*.ciamlogin.com`, `login.microsoftonline.com`), `*.azurecontainerapps.io`, `*.blob.core.windows.net` and any `wss:` address (LiveKit); it is not narrowed to specific hosts.

**Approval.** Approved by David (W2, acting for W1) on 2026-10-22, and acknowledged by Nelson (W3) on #150 the same day. Not yet acknowledged by Anthony (W1). If either declines, the fallback is to host the built app from the EU Storage account (static website), at the cost of the routing and CSP headers.

**Reverse it** by setting `web_location = "westeurope"` as soon as the region accepts new resources; the variable's validation allows it.
