# Alo.ai web app (W1)

The installable PWA: landing, sign-in, consent, child profiles, the kid
session screen, the grown-up report screen, Paystack checkout, and the
teacher view preview. Read `AGENTS.md` in this folder, PRD 4.1/4.4/4.7/14.1
and the design system (`docs/Alo.ai_Design_System/README.md`) before
changing UI.

## Run it

```sh
npm ci
npm run dev        # http://localhost:5173, syncs the design system first
npm test           # Vitest + Testing Library
npm run lint
npm run build      # type-check + production build (PWA) into dist/
```

Only an explicit `VITE_ALO_ENV=local` talks to the local emulators once
the Compose stack (`make up-web`, in `docs/LOCAL_DEV.md`) exists; the
default is non-local, so a production build can never mistake itself for
a local one (AGENTS rule 8). The browser never chooses `VOICE_MODE` or
`SESSION_PROFILE`; those are server settings.

## Design system

Followed as closely as possible, through exactly one consumption layer —
see `src/design-system/README.md` for W1's decision (verbatim bundle +
generated `tokens.css` + synced assets; no hard-coded token values).
Navigation uses `src/design-system/NavButton.tsx` (the system `Button`
with `navigate()`), never a `<button>` inside an `<a>`.

## Routes (fixture-backed MVP)

| Route | Mode | What it does | Live replacement |
|---|---|---|---|
| `/` | Grown-up | Landing. No report links: grown-up data sits behind sign-in (PRD 12) | — |
| `/signin` | Grown-up | Sample build: Google, or an email link that only signs in when clicked. Real build (Entra settings present): "Continue with Google" or "Continue with email" (a code) through Entra External ID, which signs the guardian in only after verifying them | Entra External ID (`src/auth`) |
| `/consent` | Grown-up | What consent means + the per-child records on file | Account service `consents/` |
| `/children` | Grown-up | Child profiles. Adding a child records **that child's** consent (attestation names the child and age; `consents/{consent_id}` shape with `guardian_id` + `child_id`) | Account service `children/` + `consents/` |
| `/session/:childId` | Kid | The Night session (design-system Night theme): voice orb while Kemi speaks/listens, story card from `show_passage`, moon-and-constellation reward, then "give the phone to a grown-up" with a press-and-hold gate to the report-ready card. Gated on that child's consent record. Follows **session protocol v2** (PR #24): the agent's `step` drives the screen, clip `text` fills the bubble, `show_passage` carries the story and ARL, clips fully download before play and `played` means playback finished | LiveKit room + `POST /v1/sessions` driver emitting v2 |
| `/reports`, `/reports/:sessionId` | Grown-up | Signed-in only. Report joined with its child: Coach summary + home practice free, weekly-plan activities only with an active subscription, null-safe for checks with no evidence | `reports/{session_id}` + `children/{child_id}` |
| `/plan/checkout` | Grown-up | Signed-in only. Weekly-plan checkout placeholder | Paystack inline checkout, initialized by the Account service (PRD 11.1) |
| `/schools/preview`, `/schools/preview/children/:childId` | Grown-up | Teacher view preview: sample P3B class of 23, sortable table, groups, child pages, scripted assistant. No network calls (tested) | Real teacher view comes after the hackathon (PRD 4.7) |

Fixture stores live beside their screens (`src/account/store.ts`,
`src/report/reportFixture.ts`, `src/preview/teacherFixture.ts`,
`src/session/`) and are the only places sample data enters the app.

## Sign-in: sample build or Entra External ID

`src/auth/index.ts` fixes which sign-in a build uses, from its environment variables, never at run time and never by the browser:

| Build | When | Sign-in | Where the account lives |
|---|---|---|---|
| Sample (default) | `VITE_ENTRA_CLIENT_ID` or `VITE_ENTRA_AUTHORITY` is missing, or `VITE_ALO_ENV=local` | The fixture sign-in the MVP screens run on | `localStorage`, sample data only |
| Real | Both Entra settings are present | **Microsoft Entra External ID**: Google, or a one-time code emailed to the guardian. Both go through Entra's hosted page, which verifies the guardian first | **This tab only.** Nothing is written to the browser |

Settings (all public values: the app is a public client with PKCE and holds no secret): `VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_AUTHORITY` (e.g. `https://aloai.ciamlogin.com/`), optionally `VITE_ENTRA_API_SCOPE` (the Account API's scope, once it exists; `auth().getAccessToken()` then returns a bearer token).

**Fixture or live data** is chosen by the build alone (`src/api/mode.ts`). The build is *live* only when Entra sign-in is configured, `VITE_ALO_API_URL` (the Account API's address) is set, and `VITE_ALO_ENV` is not `local`. Then children, consent and reports go through the Account API (`src/api/`, with the Entra bearer token). Any other build is the *fixture* build: no network calls for account data. The browser, URL and user never choose. The teacher preview imports no data client in either build. The reports paths (`GET /v1/reports`, `/v1/reports/{session_id}`) follow the plan for C5 and are not built yet; change them in `src/report/useReports.ts` if C5 differs.

**Until the Account service exists, the real build keeps a guardian's children and consents in memory for the life of the tab and then they are gone.** That is deliberate: a child's first name and birth year must not stay in `localStorage` on a shared family phone (PRD 12). It also means the real build cannot yet be used for real families. The sign-in session itself is in `sessionStorage` (closed with the tab). A sample build's leftovers on the same origin are removed when the real build first loads.

The consent record's `sign_in_method` is `google`, `email_code` (the real build's emailed code) or `email_link` (the sample build only). The record's shape is `schemas/consent.schema.json`.

### Setting up Entra (by hand: an external tenant cannot be made by Terraform)

1. Create an **external** tenant (Entra admin center > Overview > Manage tenants > Create > External). Its sign-in address is `https://<name>.ciamlogin.com/`: that is `VITE_ENTRA_AUTHORITY`.
2. **App registration** in that tenant: platform *Single-page application*, redirect URIs `infra/azure` output `web_redirect_uri` (and `http://localhost:5173/signin` for development). No client secret. Its application (client) id is `VITE_ENTRA_CLIENT_ID`.
3. **User flow** (Sign-up and sign-in): identity providers *Email one-time passcode* and *Google*, attribute *Email Address*. Add the app registration to it. Google needs an OAuth client from Google's console (Google Cloud console, no billing needed); its redirect URI is shown on the Google provider page in Entra.
4. Set the three `VITE_ENTRA_*` values as GitHub repository variables for the deploy workflow.

## Hosting: Azure Static Web Apps

`infra/azure/apps.tf` creates the Static Web Apps resource (Free tier, West Europe: the only EU region it is offered in). `public/staticwebapp.config.json` is its routing and headers: SPA fallback to `index.html`, long caching for hashed assets and none for `index.html` and the service worker, a Content-Security-Policy, and the microphone permission the child session needs. The workflow `.github/workflows/web-deploy-azure.yml` builds and deploys it (manual only; its header lists the variables it reads).

Not verified: the Content-Security-Policy and the routing were not run against Static Web Apps or a browser, and the deploy workflow has not run. If the policy blocks something, loosen it in `staticwebapp.config.json` and say why in the PR. `connect-src` allows any `wss:` because the LiveKit address is not fixed yet; narrow it to the LiveKit host once it is.

The real build also ships the sign-in library (about 67 kB gzipped), which the service worker precaches for everyone on first visit.
