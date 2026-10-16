# dev: local development tooling (W1, reviewed by W2 or W3)

`emulators/` (Firebase Auth/Firestore/Pub/Sub), `init.py`, `replay.py`, `webhook.py`, `smoke.py`. See `docs/LOCAL_DEV.md`, which is the spec for this folder.

- Containers are the same images Cloud Run runs; only endpoints differ. `ALO_ENV=local` enables local shortcuts, and every service must **refuse to start with `ALO_ENV=local` if `K_SERVICE` is set**. Never weaken that guard.
- `init.py` reads the same `infra/pubsub.json` as Terraform. Every start is empty and `init` seeds it; `make reset` wipes it.
- Default `AI_MODE=fixtures`. Pin image tags (fake-gcs-server, LiveKit, firebase-tools) on day 1.
- Seeds and replay fixtures are fictional. `make webhook` signs with the test secret only.
- `make smoke` must pass before merging a contract change.
