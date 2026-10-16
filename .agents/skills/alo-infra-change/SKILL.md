---
name: alo-infra-change
description: Change cloud infrastructure or a server setting (voice_mode, session_profile, demo_warm, agent_on) through Terraform. Use for anything in infra/, ops/, Cloud Run, IAM, buckets, Pub/Sub, Firestore or secrets.
---

# Alo.ai infrastructure change

Nothing in Google Cloud is created or changed by hand (PRD 15.1). W1 (Anthony) owns `infra/`; each owner adds the resources their service needs in the same PR as the code.

## Steps
1. Edit Terraform in `infra/` only (flat config, no modules). If a console change was unavoidable, copy it into Terraform the same day and record it.
2. Run `terraform fmt -check` and `terraform validate`. Do not run `terraform apply`/`destroy` yourself; CI applies on merge to main.
3. Constraints to preserve: EU region; one service account per service with least-privilege roles; Paystack secret and email key readable only by the Account and Payments service account; CI uses Workload Identity Federation (no key files); budget alerts at $100/$200/$300.
4. **Secrets:** Terraform defines secret entries and access only. Values are added with `gcloud secrets versions add` and never appear in code, tfvars or state. Anything configured outside Terraform goes into `ops/README.md`.
5. **Server settings** change via a one-line `chore/infra-...` PR to `terraform.tfvars`, reviewed like any other. Browser code must never choose `VOICE_MODE` or `SESSION_PROFILE`. After the demo set `demo_warm=false`, `session_profile="standard"`.
6. If `infra/pubsub.json` changes, check `dev/init.py` still reads it correctly (both use the same file).
7. Use `alo-branch-and-pr` to open the PR; W1's PRs go to W2 or W3 for review. Add a rollback note: re-apply the previous commit (or move Cloud Run traffic back first in an emergency, then make Terraform match).
