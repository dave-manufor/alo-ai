# Taking the web app live (mini-study)

One page, in the order to do it. "You" is the person with Owner on the Azure subscription (David). Everything in Azure is created or changed by Terraform in `infra/azure/`; the steps below that are not Terraform are the ones nothing can do for you (portal sign-in setup, secret values, running `terraform apply`).

Where the pieces are, for the commands below: resource group `aloai-rg`; apps and jobs are listed by `az containerapp list -g aloai-rg -o table` and `az containerapp job list -g aloai-rg -o table`; the addresses are Terraform outputs (`terraform -chdir=infra/azure output`).

## 0. Before anything

- [ ] The pull requests for this go-live are merged: the session status and web fixes (#177), the Coach outbox (#178), the join timeout (#179), and this one.
- [ ] CI is green on `main`. GitHub Actions runs again because the repository is public. If it ever fails to start (billing), use the by-hand routes marked **Without Actions** below.
- [ ] The privacy gates in `docs/privacy/ndpa-transfer-basis.md` are read, and the open ones are accepted on purpose (the Gemini decision is in its decision log).

## 1. Images

1. Run **Deploy images** (`deploy-images.yml`) on `main`. It prints the digests as an `images = { ... }` block.
   **Without Actions:** from a checkout of `main`, `az acr build --registry <acr name> --image aloai-<service>:<sha> --file services/<service>/Dockerfile .` for `account`, `core`, `session_agent` and `reading_scorer`, then read the digest with `az acr repository show --name <acr name> --image aloai-<service>:<sha> --query digest -o tsv`.
2. Put the block in `infra/azure/images.auto.tfvars` (git-ignored).
3. `terraform -chdir=infra/azure plan -out=live.tfplan` and read it. It should change only the apps and jobs (and the Core app's `NOTIFIER` setting). Anything that replaces a resource: stop and ask.
4. **Do not apply during a session or a rehearsal**: the Session Agent runs in single-revision mode, so a deploy ends a running session. You run `terraform apply live.tfplan` yourself (type it in your own terminal).
5. Check: `az containerapp list -g aloai-rg -o table` shows every app `Running`, and `curl -s https://<account_url>/healthz` answers `ok`.

## 2. Seed (only if it has not run since the last image or clip change)

`az containerapp job start --name aloai-seed --resource-group aloai-rg`, then check `az containerapp job execution list --name aloai-seed -g aloai-rg -o table` ends `Succeeded`. Until it has, a session has no clips and no bank passage and cannot start.

## 3. Sign-in (portal, by hand: Entra External ID, tenant `aloaiauth`)

- [ ] **SPA app registration** (the web app): platform *Single-page application*, redirect URIs: the `web_redirect_uri` output (`https://<web host>/signin`), `http://localhost:5173/signin`, and the bare origin `https://<web host>` (sign-out returns there). No client secret.
- [ ] **API app registration**: exposes the scope `access_as_user`; the SPA is allowed to ask for it; `email` is sent as an optional claim in the access token (the Account service answers `EMAIL_MISSING` without it).
- [ ] **User flow** (sign-up and sign-in): *Email one-time passcode* only, attribute *Email Address*, no Google; the SPA app registration is added to it.
- [ ] The values: `entra_tenant_id`, `entra_authority`, `entra_api_audience` are in `terraform.tfvars` already; the SPA's client id is the one new value.

## 4. The web app

1. GitHub repository variables (Settings > Secrets and variables > Actions > Variables), all public values:
   `VITE_ENTRA_CLIENT_ID` (the SPA's client id), `VITE_ENTRA_AUTHORITY` (`https://aloaiauth.ciamlogin.com/<entra_tenant_id>/`, with the tenant id: the bare address fails with `endpoints_resolution_error`), `VITE_ENTRA_API_SCOPE` (`api://<entra_api_audience>/access_as_user`), `VITE_ALO_API_URL` (the `account_url` output, no trailing slash), plus `AZURE_RESOURCE_GROUP` (`aloai-rg`) and `AZURE_WEB_APP_NAME` (the `web_app_name` output).
2. Run **Deploy web app to Azure** (`web-deploy-azure.yml`). It fails at its first step if one of the four `VITE_*` variables is missing, because without them the site would be the sample build.
   **Without Actions:** from `apps/web`, with the four values exported as `VITE_*`: `npm ci && npm run build`, then `token=$(az staticwebapp secrets list --name <web_app_name> --resource-group aloai-rg --query properties.apiKey -o tsv)` and `npx @azure/static-web-apps-cli@2.0.8 deploy dist --deployment-token "$token" --env production`.
3. Check that it is the live build, not the sample one: open the site; the sign-in screen must send you to `aloaiauth.ciamlogin.com`, not show a code on screen.

## 5. Smoke test, with a fictional child, before any real family

From the repository root, with your `az login` (Cosmos data contributor and Service Bus data owner; `infra/azure/README.md` has the operator setup) and the LiveKit key and secret read from Key Vault into the shell (never into a file):

```
CLOUD=azure AZURE_COSMOS_ENDPOINT=... AZURE_SERVICEBUS_NAMESPACE=... \
AZURE_SPEECH_REGION=... AZURE_SPEECH_RESOURCE_ID=... \
LIVEKIT_URL=wss://... LIVEKIT_API_KEY=... LIVEKIT_API_SECRET=... \
PYTHONPATH=libs/aloai python services/session_agent/tools/cloud_smoke.py
```

It must exit 0: session finished, report and plan written, both dead-letter queues empty. It does not test the web app, sign-in or the Account API; step 6 does.

## 6. One real run through the live site (adult rehearsal)

With a fictional child, on the study phone (Android Chrome), on the venue's network:

1. Open the site, **Parent or guardian**, enter your email, enter the code from your inbox.
2. Add a fictional child (consent tick, name, class, birth year). The child must appear after a reload (it is stored in the Account service, not the browser).
3. Get ready, Start, allow the microphone, read the story out loud, answer, hand back.
4. The reports screen says the report is being made, then shows it. The plan follows within a few minutes.
5. In the browser's developer tools (or `chrome://inspect` for the phone): no red errors in the console, no blocked requests (Content-Security-Policy).
6. Delete the fictional child afterwards with `ops/delete_child.py` (see the runbook).

If anything fails, stop and use the runbook's "when something is wrong" table. Do not invite families until this passes on the phone and network you will actually use.

## Rolling back

- The web app: redeploy the previous build (`web-deploy-azure.yml` from the previous commit, or the by-hand route with that commit checked out).
- A service: re-apply the previous images block (`images.auto.tfvars` from before) with `terraform plan` and `apply`; in an emergency, move traffic to the previous revision (`az containerapp revision activate` and `az containerapp ingress traffic set`) and make Terraform match the same day.
- To stop live spend at once: `agent_on = false` and `demo_warm = false` in `terraform.tfvars` (a one-line `chore/infra-...` PR, applied by you); the apps scale to zero.

## Not part of going live (later)

Payments (Z1), real email (Z2: today the Coach leaves the report-ready request in `outbox/`), the teacher view (Z3), Gemini Live (Z4), the Passage Generator (Z5), private networking and a custom domain (Z6: the CSP and the Account `WEB_ORIGIN` allow one web address), alerts and diagnostic logs (J1, I5: the runbook says how to look by hand).
