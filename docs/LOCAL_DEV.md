# Running Alo.ai on your laptop

One Docker Compose stack, three profiles: one per owner. Each person runs their own services from source, with hot reload, and gets everything they depend on either running for real or stubbed with fixtures that are checked against the same schemas production uses.

**The rule that keeps local honest:** the containers are the same images Cloud Run runs. Only the endpoints change: emulators instead of Firestore, Pub/Sub, Firebase Auth and Cloud Storage, and a local LiveKit server instead of LiveKit Cloud.

## What runs where

| Piece | Cloud | Laptop |
|---|---|---|
| Session Agent; Account and Payments; Reading Scorer; Core | Cloud Run (4 services), plus the book ingestion job | Same Dockerfiles, run by Compose |
| Firestore, Pub/Sub, Firebase Auth | Managed | Firebase Emulator Suite (one container) |
| Cloud Storage (audio, clips, books) | 3 buckets | `fake-gcs-server`, data kept in a volume so the clip store survives restarts |
| LiveKit | LiveKit Cloud | `livekit-server --dev` |
| Pub/Sub topic and push subscriptions | Terraform reads `infra/pubsub.json` | `dev/init.py` reads the **same file**, so they can't drift |
| Gemini, Gemini Live, Speech-to-Text, Chirp 3 HD | Vertex AI | `AI_MODE=fixtures` (canned, free) or `AI_MODE=live` (the cloud project, your own login) |
| Reading Scorer hardware | CPU only (no GPU anywhere) | The same image |
| Paystack | Test mode | Test mode for API calls; webhooks sent by `make webhook` |

## Who runs what

| Owner | Command | Runs from source (hot reload) | Also running | Stubbed with fixtures |
|---|---|---|---|---|
| W1: web, accounts, payments | `make up-web` | web, account (the Account and Payments service) | emulators, storage | A finished session for Chidi is seeded, so the report and Coach screens have data with the real shape. No LiveKit or scorer. |
| W2: live session | `make up-session` | session-agent, core (generator), book ingestion (`make books`) | LiveKit, account, web, emulators, storage | The scorer isn't running; the session doesn't need it (it only scores after reading), so its event waits in the local topic (`make events`). Add `SCORER=1` to run it too (about 3 GB more memory). |
| W3: after the session | `make up-after` | scorer, core (grader, Coach) | web, account, emulators, storage | `make replay SESSION=chidi` uploads a recorded session's audio and publishes its event, so the scorer and Grader run without anyone reading aloud. |
| Everyone | `make up-all` | everything | | Used for `make smoke` and before merging a contract change. |

## Toggles

| Variable | Values | Default locally | What it does |
|---|---|---|---|
| `AI_MODE` | `fixtures`, `live` | `fixtures` | `fixtures` answers every AI call from `fixtures/ai/` (the same files CI uses); Gemini Live is off, so the session runs in scripted-clip mode, which is also the production fallback path. `live` calls Vertex AI on the cloud project and spends from the $400. |
| `VOICE_MODE` | `cache_first`, `live_first` | `cache_first` | Who speaks scripted lines: pre-made clips, or Gemini Live with the clip as fallback. "That word is X." always plays from the clip. In the cloud it comes from Terraform (`voice_mode`); the browser never sets it. |
| `SESSION_PROFILE` | `standard`, `demo` | `standard` | `demo`: a 75-word story, 2 questions, a ~50-word listening story when triggered. In the cloud it comes from Terraform (`session_profile`). |
| `demo_warm` | Terraform variable | n/a | The infrastructure toggle: min 1 instance on all four services from the evening before the demo. Never set locally. |

`ALO_ENV=local` turns on the local-only shortcuts (no OIDC check on Pub/Sub pushes, emulator URLs for clips, fixture AI). **Every service refuses to start with `ALO_ENV=local` if `K_SERVICE` is set**, which Cloud Run always sets, so these shortcuts can never reach the cloud.

## Repository layout this assumes

```
apps/web/                   W1
services/account/           W1 (accounts and payments)
services/session_agent/     W2
services/core/              generator/ and books/ (W2), grader/ and coach/ (W3)
services/reading_scorer/    W3
libs/aloai/                 aloai_scoring, aloai_authz, aloai_guardrails, shared clients
schemas/                    one JSON Schema per contract in PRD 14.2
fixtures/                   seed/, contracts/, ai/, recordings/
eval/                       agent evaluation sets, red-team set, golden recordings index
dev/                        emulators/, init.py, replay.py, webhook.py, smoke.py
infra/                      flat Terraform, including pubsub.json shared with dev/init.py
ops/                        paystack/, delete_child.py, README.md
docker-compose.yml  Makefile  .env.example
```

Compose service names stay short (`web`, `account`, `session-agent`, `core`, `scorer`); only the folders they build from have the longer names above.

## `docker-compose.yml`

```yaml
name: aloai

x-local-env: &local-env
  ALO_ENV: local
  AI_MODE: ${AI_MODE:-fixtures}
  VOICE_MODE: ${VOICE_MODE:-cache_first}
  SESSION_PROFILE: ${SESSION_PROFILE:-standard}
  GOOGLE_CLOUD_PROJECT: aloai-dev
  GOOGLE_CLOUD_LOCATION: europe-west1
  GOOGLE_APPLICATION_CREDENTIALS: /secrets/adc.json     # only read when AI_MODE=live
  FIRESTORE_EMULATOR_HOST: emulators:8080
  FIREBASE_AUTH_EMULATOR_HOST: emulators:9099
  PUBSUB_EMULATOR_HOST: emulators:8085
  STORAGE_EMULATOR_HOST: http://gcs:4443
  AUDIO_BUCKET: aloai-dev-audio
  CLIPS_BUCKET: aloai-dev-clips
  BOOKS_BUCKET: aloai-dev-books
  CORE_URL: http://core:8080
  SCORER_URL: http://scorer:8080
  ACCOUNT_URL: http://account:8080

x-adc: &adc ${GCLOUD_ADC}:/secrets/adc.json:ro

x-after-init: &after-init
  init: { condition: service_completed_successfully }

services:
  # ---------- always on ----------
  emulators:
    build: ./dev/emulators
    ports: ["4000:4000", "8080:8080", "9099:9099", "8085:8085"]   # UI, Firestore, Auth, Pub/Sub
    healthcheck:
      test: ["CMD", "node", "-e", "fetch('http://localhost:8080').then(()=>process.exit(0)).catch(()=>process.exit(1))"]
      interval: 3s
      retries: 40

  gcs:
    image: fsouza/fake-gcs-server:latest          # pin the tag on day 1
    command: -scheme http -port 4443 -backend filesystem -filesystem-root /storage -external-url http://localhost:4443
    ports: ["4443:4443"]
    volumes: ["gcs-data:/storage"]

  init:                                           # one-shot: buckets, topic, push subscriptions, seed data
    build: { context: ., dockerfile: services/core/Dockerfile }
    command: python -m dev.init
    environment: *local-env
    volumes: ["./dev:/app/dev:ro", "./infra/pubsub.json:/app/infra/pubsub.json:ro", "./fixtures:/app/fixtures:ro"]
    depends_on:
      emulators: { condition: service_healthy }
      gcs: { condition: service_started }

  # ---------- W1 ----------
  web:
    image: node:20-bookworm-slim
    working_dir: /web
    command: sh -c "npm ci && npm run dev -- --host 0.0.0.0"
    environment:
      VITE_ALO_ENV: local                         # web app connects to the Auth and Firestore emulators
    ports: ["5173:5173"]
    volumes: ["./apps/web:/web", "web-node-modules:/web/node_modules"]
    profiles: [web, session, after, all]

  account:                                        # Account and Payments service
    build: { context: ., dockerfile: services/account/Dockerfile }
    environment: *local-env
    env_file: .env                                # PAYSTACK_SECRET_KEY: test key only
    ports: ["8081:8080"]
    depends_on: *after-init
    develop:
      watch:
        - { action: sync+restart, path: ./services/account, target: /app/services/account }
        - { action: sync+restart, path: ./libs, target: /app/libs }
    profiles: [web, session, after, all]

  # ---------- W2 ----------
  livekit:
    image: livekit/livekit-server:latest          # pin the tag on day 1
    command: --dev --bind 0.0.0.0 --node-ip 127.0.0.1
    ports: ["7880:7880", "7881:7881", "7882:7882/udp"]
    profiles: [session, all]

  session-agent:
    build: { context: ., dockerfile: services/session_agent/Dockerfile }
    command: python -m services.session_agent.main dev   # prod runs `start`; `dev` adds reload
    network_mode: service:livekit                 # shares LiveKit's network, so 127.0.0.1 works for media
    environment:
      <<: *local-env
      LIVEKIT_URL: ws://127.0.0.1:7880
      LIVEKIT_API_KEY: devkey
      LIVEKIT_API_SECRET: secret
    env_file: .env
    volumes: [*adc]
    depends_on:
      init: { condition: service_completed_successfully }
      livekit: { condition: service_started }
    develop:
      watch:
        - { action: sync, path: ./services/session_agent, target: /app/services/session_agent }
        - { action: sync+restart, path: ./libs, target: /app/libs }
    profiles: [session, all]

  # ---------- W2 + W3 ----------
  core:                                           # Passage Generator, Grader, Reading Coach (the ingestion job uses this image)
    build: { context: ., dockerfile: services/core/Dockerfile }
    environment: *local-env
    env_file: .env
    ports: ["8083:8080"]
    volumes: [*adc]
    depends_on: *after-init
    develop:
      watch:
        - { action: sync+restart, path: ./services/core, target: /app/services/core }
        - { action: sync+restart, path: ./libs, target: /app/libs }
    profiles: [session, after, all]

  # ---------- W3 ----------
  scorer:
    build: { context: ., dockerfile: services/reading_scorer/Dockerfile }   # CPU-only PyTorch, same image as Cloud Run
    environment: *local-env
    ports: ["8084:8080"]
    volumes: [*adc]
    mem_limit: 4g
    depends_on: *after-init
    develop:
      watch:
        - { action: sync+restart, path: ./services/reading_scorer, target: /app/services/reading_scorer }
        - { action: sync+restart, path: ./libs, target: /app/libs }
    profiles: [after, all, scorer]

volumes:
  gcs-data:
  web-node-modules:
```

### `dev/emulators/Dockerfile`

```dockerfile
FROM eclipse-temurin:21-jre                       # Java for the Firestore and Pub/Sub emulators
COPY --from=node:20-bookworm-slim /usr/local /usr/local
RUN npm install -g firebase-tools                 # pin the version on day 1
WORKDIR /emulators
COPY firebase.json .
RUN firebase setup:emulators:firestore && firebase setup:emulators:pubsub && firebase setup:emulators:ui
CMD ["firebase", "emulators:start", "--project", "aloai-dev", "--only", "auth,firestore,pubsub"]
```

`firebase.json` sets `"host": "0.0.0.0"` on each emulator, with ports 9099 (Auth), 8080 (Firestore), 8085 (Pub/Sub) and 4000 (UI). Every start is empty and `init` seeds it, so everyone's stack starts from the same state. `make reset` wipes it.

### `.env.example` (copy to `.env`, never commit `.env`)

```
GCLOUD_ADC=/Users/you/.config/gcloud/application_default_credentials.json   # after `gcloud auth application-default login`
PAYSTACK_SECRET_KEY=sk_test_...
PAYSTACK_PUBLIC_KEY=pk_test_...
RESEND_API_KEY=                                    # leave empty locally; emails are printed to the log
```

## Make targets

| Target | What it does |
|---|---|
| `make up-web`, `make up-session`, `make up-after`, `make up-all` | `docker compose --profile <x> up --build` and `docker compose watch` |
| `make seed` | Re-seeds the emulators: a test parent (sign in with the emulator's fake Google account), a child, consent, an active subscription, and Chidi's finished session |
| `make replay SESSION=chidi` | Uploads a recording from `fixtures/recordings/` and publishes its session event, exactly as the Session Agent would |
| `make webhook EVENT=charge.success REF=...` | Posts a Paystack event to the local Account and Payments service, signed with your test secret (HMAC-SHA512 in `x-paystack-signature`) |
| `make books` | Runs the real ingestion job on the 30-title catalogue (W2; needs `AI_MODE=live` once for the embeddings, about a cent) |
| `make events` | Shows what's been published to the local topic |
| `make smoke` | In fixtures mode: sign in, check out, signed webhook, plan unlocked; then replay a session, scorer, Grader, report written. About 2 minutes. |
| `make reset` | Stops everything and clears the emulators (keeps the word-clip store volume) |

## Keeping the stubs honest

- Every hand-off in the PRD 14.2 contracts table has a JSON Schema in `schemas/` and a sample in `fixtures/contracts/`.
- CI checks every fixture against its schema, and each producer's real output against the same schema (contract tests). If W2 changes what the Session Agent publishes, W3's replay fixture fails CI until it's updated. A stub can't quietly drift from the real thing.
- The seeded data and fixtures contain no real child's name, audio or transcript. The mini-study recordings never go in Git.

## What the laptop can't show you

| Gap | Where it gets checked |
|---|---|
| Real Gemini Live latency, Chirp voice quality | `AI_MODE=live` on your laptop, briefly |
| Cloud Run cold starts, IAM between services, OIDC on Pub/Sub pushes | Every merge to `main` deploys to the cloud project, so these show up the same day |
| Scoring time on Cloud Run's CPU (2 vCPU) | Measure on day 1 against the cloud project; the target is a report within 45 s of the session ending |
| Phones on mobile data, LiveKit Cloud networking | Test on a real phone against the cloud project from day 3 |

## Laptop requirements

- Docker Desktop, OrbStack or Colima, with Compose 2.22 or newer (for `watch`). Apple Silicon is fine.
- 8 GB of RAM is enough for `up-web` and `up-session`. `up-after` and `up-all` need 16 GB, because the scorer's alignment model uses about 3 GB.
- The first scorer build downloads its alignment model into the image (about 1 GB, once).
- If LiveKit media doesn't connect in Docker on your machine, run `livekit-server --dev` natively (`brew install livekit`) and set `LIVEKIT_URL` to it. Check this on day 1.
