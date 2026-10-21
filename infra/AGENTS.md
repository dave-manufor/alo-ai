# infra: Terraform (W1, reviewed by W2 or W3)

One flat configuration for project `aloai-dev` (no modules, no per-env files). Read PRD 15, 14.5 and the root `AGENTS.md` first.

- **Nothing in Google Cloud is created or changed by hand.** If a manual fix was unavoidable, copy it into Terraform the same day. Use `alo-infra-change`.
- Pin Terraform (`.terraform-version`) and the `google` provider (`versions.tf`); commit `.terraform.lock.hcl`. State is in the EU bucket `aloai-tfstate-eu`.
- Secret **values** never go in Terraform or its state (`gcloud secrets versions add`). Terraform defines the secret entries and who may read them. Paystack secret readable only by the Account service account.
- Server settings (`voice_mode`, `session_profile`, `demo_warm`, `agent_on`) change only through a one-line `chore/infra-...` PR to `terraform.tfvars`. `demo_warm = false` and `session_profile = "standard"` again after the demo.
- EU region only. One service account per service with least-privilege roles; CI deploys via Workload Identity Federation (no key files). Budget alerts at $100, $200, $300.
- **Azure (`CLOUD=azure`) lives in `infra/azure/`**, a second flat root with its own `README.md` (bootstrap, secrets, known gaps, rollback). The same rules apply there with Azure's names: no console changes, managed identities and no keys, EU regions only, secret values outside Terraform (`az keyvault secret set`), `terraform fmt -check` and `terraform validate` before a PR. `infra/events.json` (queue to event types) is read by both Terraform and the services (`EVENT_ROUTES`); the Google build still uses `infra/pubsub.json`.
- `infra/pubsub.json` is also read by `dev/init.py`; keep them in sync by editing only this file.
- Before a PR: `terraform fmt -check` and `terraform validate`. Each owner adds the resources their service needs in the same PR as their code.
