# infra/azure: Alo.ai on Azure (`CLOUD=azure`)

One flat Terraform configuration for the Azure build, next to the Google Cloud one described in PRD 15.1. Read `docs/adr/0001-azure-as-a-second-cloud.md` for why and for the service map. Nothing here is created or changed by hand in the portal; if a manual fix is unavoidable, copy it into Terraform the same day.

Planned and applied by hand against the study subscription (2026-10-22, by David with `terraform apply` run from his own terminal; CI does not apply). `terraform fmt` and `terraform validate` run in CI. For the steps to put the web app live and run a study day, see `docs/ops/go-live.md` and `docs/ops/study-day-runbook.md`.

## What it creates

| File | What |
|---|---|
| `main.tf` | Resource group, a managed identity per service and one for CI (GitHub OIDC), Container Registry, Blob Storage (`audio` private with a 90-day lifecycle, `clips` public read, `books` private), Cosmos DB (`docs`, and `books` with a vector index through `azapi`), Service Bus queues from `../events.json`, Key Vault entries, Azure OpenAI and Speech with their deployments, every role assignment, the budget |
| `apps.tf` | Log Analytics, the Container Apps environment, the four services, the book-ingestion job, and the Static Web Apps resource for the web app (`westus2`, Free tier: West Europe refused it; the static files hold no child data, see the ADR exception) |
| `variables.tf`, `terraform.tfvars` | The server settings (`voice_mode`, `session_profile`, `demo_warm`, `agent_on`) and the rest |
| `outputs.tf` | What CI and the web app need |

Rules it keeps: EU region only (validated); one identity per service; no keys or connection strings anywhere (local authentication is off on Cosmos DB, Service Bus, Storage, OpenAI and Speech); only the Account service reads the Paystack secret and the email key; CI deploys with GitHub OIDC and no key files; budget alerts at $50, $100 and $130 of the $150 credit.

## Bootstrap, once, by a person with Owner on the subscription

1. Create the state storage (`aloai-tfstate-rg`, storage account `aloaitfstateeu`, container `tfstate`, versioning on, EU). Rename it in `backend.tf` if the account name is taken: storage account names are global.
2. `az login`, then from `infra/azure`: `terraform init`, then the vault first: `terraform apply -target=azurerm_key_vault.main -var 'budget_contact_emails=["<an address>"]'`.
3. Set the secret values (see "Secret values" below). The vault must hold all four before the apps are created, because the Container Apps read them.
4. Then the full `terraform apply -var 'budget_contact_emails=["<an address>"]'`. The first apply is done by a person, because it creates the CI identity and its roles. Every later apply is also done by a person (CI only plans checks and builds images; no workflow runs `terraform apply`).
5. In GitHub, set the repository variables `AZURE_CLIENT_ID` (output `ci_client_id`), `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, and `TF_VAR_budget_contact_emails`. The address is a person's, so it is not in `terraform.tfvars`.
6. Register `Microsoft.App`, `Microsoft.DocumentDB`, `Microsoft.ServiceBus`, `Microsoft.CognitiveServices` and `Microsoft.ContainerRegistry` on the subscription if they are not.

## Outside Terraform

- **Secret values.** Terraform does not create or read the Key Vault entries (a managed secret resource reads the value into state on every refresh, even with `ignore_changes`). It only grants access to, and points the Container Apps at, `<vault uri>secrets/<name>`. You need `Key Vault Secrets Officer` on the vault to set them. Create each entry once, so no value reaches state:
  `az keyvault secret set --vault-name <key_vault output> --name paystack-secret-key --value ...`, and the same for `resend-api-key`, `livekit-api-key`, `livekit-api-secret`. Paystack stays in test mode. Container Apps read the latest version.
- **LiveKit.** The server and its account are set up in LiveKit's dashboard; put its `wss://` address in `livekit_url`.
- **Entra External ID sign-in for the web app** (an external tenant, an app registration, a user flow with email code and Google): set up by hand, steps in `apps/web/README.md`. Register the output `web_redirect_uri` as its redirect URI. The web app is deployed by `.github/workflows/web-deploy-azure.yml` (manual; it reads the Static Web Apps token at run time).
- **Container images.** CI builds and pushes them to the registry (`acr_login_server`) and passes each digest back in `var.images`. Until then the apps run a placeholder image.
- **The first clips and books.** The seed job makes the clips and writes the bank passages (see "After the first apply: seed the stores"); someone runs it after the first apply. The book ingestion run and the 30-book catalogue are not built yet.

## Smoke test

`services/session_agent/tools/cloud_smoke.py` drives a fictional child through a whole session and checks the result: the session ran to the end, the report and the parent plan were written, and both dead-letter queues (`core-events`, `scorer-events`) are empty. It exits non-zero if any check fails. Run it after an apply and after the images are deployed, and not during a rehearsal. The agent worker must be running, and so must Core, the Scorer and LiveKit.

- It needs your `az login` to have `Cosmos DB Built-in Data Contributor` on the account and `Azure Service Bus Data Owner` on the namespace (the queue counts are a management call), and `Cognitive Services Speech User` on the Speech resource for the child's voice.
- The settings are in the docstring: the Cosmos endpoint, the Service Bus namespace name, the Speech region and resource id, and the LiveKit address, key and secret. Read the key and secret from the vault into the shell (`az keyvault secret show`), not into a file.
- It leaves one session, report and plan per run, and one fictional child (`child_smoke`, guardian `guardian_smoke`). Nothing of a real child is used and nothing is deleted.
- `--silent` keeps the child's microphone silent: the session then ends early and may be INCOMPLETE. The default has the child speak, with Azure AI Speech making the audio at run time.

## Before you rely on it (checked against nothing yet)

- **Model availability and EU processing.** `openai_deployments` asks for `DataZoneStandard`, which keeps processing in the EU data zone. The listed models and versions may not all be offered in `swedencentral`; `gpt-4o-transcribe` in particular may be `GlobalStandard` only. `GlobalStandard` may process outside the EU, which the EU rule and the NDPA transfer basis do not allow, and the variable's validation refuses it. If a model is only global, that is a decision for the team, not something to change quietly.
- **KEDA and Service Bus.** Core and the Scorer scale from zero on queue length, with the managed identity. They hold `Azure Service Bus Data Owner` on their own queue because I believe KEDA needs it to read the length; try a narrower role first. If scaling from zero does not work, `demo_warm` (minimum 1) is the fallback, and events wait in the queue meanwhile.
- **The `books` vector container** uses `azapi` with API `2024-11-15` and a `quantizedFlat` index. Check that the container and `VectorDistance` queries work before the catalogue is loaded.
- **`resource_manager_id`** on the storage containers is deprecated in azurerm 4.81 and still works; it is used for the role scopes.
- **Free tier.** Cosmos DB's free tier is one per subscription: the apply fails if the subscription already has one.
- **Names.** Registry, storage, Cosmos DB, Service Bus, Key Vault and the AI accounts get a suffix from the subscription id so they are unique.

## Known gaps

- **Service-to-service calls are not authenticated on Azure.** Core's quick-grade endpoint and Reading Scorer are internal to the environment (no external ingress), which is all that protects them. The Session Agent sends no token to Core until `CORE_AUDIENCE` is set. Entra app registrations for the callee audience, role assignments for the callers, and the `aloai_service_auth.entra_caller` check in Core are still to do, and need permission to create app registrations.
- **Public endpoints.** The data services have public endpoints protected by Entra only: no virtual network, private endpoints or firewalls. Fine for a hackathon on synthetic and consented data; not for the pilot.
- **No duplicate detection** on the Basic Service Bus tier; consumers drop repeats by `event_id`.
- **Session Agent and the single revision.** `revision_mode = "Single"`: a deploy replaces the worker, and a running session on it ends. Do not deploy during a rehearsal.

## Cost

Estimated about $35 to $50 of the $150 for the sprint (Container Apps, the registry, Speech, Azure OpenAI at about $0.05 to $0.15 a session; the rest is near zero). Recheck prices before relying on it. The budget emails at $50, $100 and $130.

## Rollback

Re-apply the previous commit's configuration (`git revert`, merge, CI applies). In an emergency move a service's traffic back to its previous revision in the portal first (`az containerapp revision activate` and `az containerapp ingress traffic set`), then make Terraform match the same day. To turn off live spend quickly set `demo_warm = false` and `agent_on = false`; the apps scale to zero.

## After the first apply: seed the stores

Two manual jobs, run when needed (`az containerapp job start --name <name> --resource-group aloai-rg`; the names are in the `jobs` output):

1. **`seed`**: makes the clips with the Azure voice and writes the bank passages (`services/session_agent/seed.py`). Run it after the first apply, and again after changing `voice_profile_id`, `tts_voice` or the bank passages. Clips already there are never replaced, so it is safe to repeat. Until it has run, a session on Azure has no clips and no bank passage and cannot start. Check `az containerapp job execution list` for a failed run: the job exits non-zero if any clip or passage failed.
2. **`book_ingest`**: embeds the catalogue with `text-embedding-3-small` once there is one in Cosmos DB (`services/core/books/reembed.py`). **There is no catalogue yet:** the ingestion job and the 30 real open-licence books it would load do not exist, so this job finds nothing to do. It uses the Core image (`services/core/Dockerfile`).

Both jobs are untested against Azure.

## Deploying images

`.github/workflows/deploy-images.yml` builds the four service images on a merge to `main` that touches the services (or by hand from the Actions tab, on `main`), pushes them to the registry as `aloai-<service>:<git sha>` over GitHub OIDC, and prints their digests as an `images = { ... }` block (in the run's summary, and as the `images-tfvars` artifact). It changes no Azure resource. To run them:

1. Copy the block into a file such as `images.auto.tfvars` in `infra/azure` (git-ignored: do not commit digests), or pass it with `-var`.
2. `terraform plan -out=...`, read it (it should only change the apps and jobs), then apply it. The apps get a new revision on the new image; **do not deploy during a rehearsal or a session** (the Session Agent runs in single revision mode, so a deploy ends a running session).
3. After the first real images: run the seed job once (`az containerapp job start --name aloai-seed --resource-group aloai-rg`). Until it has run there are no clips and no bank passage.

The repository variables it reads (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_ACR_NAME`, plus `AZURE_RESOURCE_GROUP` and `AZURE_WEB_APP_NAME` for the web deploy) are set from the Terraform outputs. The CI identity can only sign in from the `main` branch, so the workflow cannot be tried from a pull request.

## The generator switch

`generator_on` (default `false`, in `terraform.tfvars`, changed only by a one-line `chore/infra-...` PR) lets `plan.ready` pre-generate a child's next story and the Session Agent ask the Passage Generator for the story. Leave it `false` until the generator and tagger evaluation sets have been run on the Azure deployments (`generator`, `tagger`) and word clips are made for generated stories: the seed job covers only the bank passages, so a generated story's words would have no clips.
