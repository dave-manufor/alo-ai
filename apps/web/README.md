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

The session screen follows the "Àlọ́ Night Session V" design. `src/session/DESIGN-V.md` maps its palette to the Night tokens and lists the proposed additions to the system (breakpoint primitives, an icon-only play button, a `sr-only` utility). One deliberate deviation: the child's screen shows no subtitles; what Auntie Kemi says goes to a visually hidden `aria-live="polite"` region (design-system README, Accessibility). Layout contract: `src/styles/session.css` (short screen, landscape phone and tablet rules, safe areas, `dvh`, `prefers-reduced-motion`); it has been designed for 360 x 640, 412 x 915, 768 x 1024 and 915 x 412 but **not yet checked in a real browser** (B12).

## Routes (fixture-backed MVP)

| Route | Mode | What it does | Live replacement |
|---|---|---|---|
| `/` | Grown-up | First screen: **Parent or guardian** (sign in) or **School or teacher** (the preview). A signed-in guardian goes on to their Home. No data on it (PRD 12) | — |
| `/signin` | Grown-up | **Email and a one-time code; no Google, no password.** Sample build: email, then a code step (the sample code is shown, nothing is emailed); signed in only when the code is right. Real build (Entra settings present): our screen takes the email and sends the guardian to Entra External ID with it as `loginHint`; Entra emails the code and signs them in only after verifying it | Entra External ID (`src/auth`) |
| `/onboarding/consent`, `/onboarding/child` | Grown-up | Step 1 of 2: what we keep and the parent-or-guardian tick. Step 2: first name, class (P1 to P6), birth year; saving records **that child's** consent (the attestation names the child and age, shown in full first). Consent is per child, so `/children/new` asks again | Account service `children/` + `consents/` |
| `/home`, `/reports`, `/plan`, `/account` | Grown-up | The signed-in app. A tab bar fixed to the bottom on phones; the same four links in the top bar from 48rem up. Home (child, last/next check, tip), Reports, the weekly plan, and Account (children, recordings choice, delete with an in-page confirm, plan, sign out) | Account service. Live build: edit a child and the recordings choice work (`PATCH /v1/children/{id}`, `POST /v1/consents`); deleting data says to ask the study team (`ops/delete_child.py`). After a reading check, `/reports?pending=<session id>` polls `GET /v1/sessions/{id}` and says "being made" until the report exists |
| `/ready/:childId` | Grown-up | Get ready: tips, who is reading, connection check, then the session. No tab bar | — |
| `/children/new`, `/children/:childId/edit` | Grown-up | Add another child, or edit one (sample build only) | `POST /v1/children`, `PATCH /v1/children/{id}` |
| `/privacy`, `/terms` | Grown-up | Plain-words summaries linked from sign-in and consent (need legal review before a pilot) | — |
| `/children`, `/consent`, `/schools/preview*` | — | Redirects to the screens above, so old links keep working | — |
| `/session/:childId` | Kid | The Night session (design-system Night theme). Start, then a short microphone explainer before the browser prompt (a grown-up recovery screen if the mic is blocked or missing). Voice orb while Kemi speaks/listens, the story in measured pages (tap to turn, dots only) from `show_passage`, moon-and-constellation reward, then "give the phone to a grown-up" with a press-and-hold gate (pointer, or hold Space/Enter) to the hand-back card ("the report is being made"). Gated on that child's consent record. Follows **session protocol v3** (v2 accepted): the agent's `step` drives the screen, clip `text` goes to a hidden live region (no subtitles), clips download in the background (four at a time, in the order listed; a `play` jumps the queue and waits only for its own clip; a failed download is forgotten so the agent's retry works; the passage waits at most 8 s for its word clips) and `played` means playback finished. The build picks the driver: fixture replay, or LiveKit (`src/session/liveDriver.ts`) in a live build | LiveKit room + `POST /v1/sessions` (live build) |
| `/reports/:sessionId` | Grown-up | Signed-in only. Report joined with its child: Coach summary, profile and one home practice free; the weekly plan and books only with an active subscription (`/plan`); null-safe for checks with no evidence. In the sample build each child gets one sample report (`src/report/childReports.ts`) | Live build: Account API reports (`src/report/useReports.ts`) + `/v1/children` |
| `/upgrade`, `/plan/checkout` | Grown-up | Signed-in only. The plan's price card, then the Paystack placeholder. The sample build adds a labelled "switch the plan on" button | Paystack inline checkout, initialized by the Account service (PRD 11.1) |
| `/schools`, `/schools/children/:childId` | Grown-up | Teacher view preview, **no sign-in**, sample banner on every screen: sample P3B class of 23, stat tiles, a sortable table (one card per child on a phone), groups, child pages, scripted assistant. No network calls (tested) | Real teacher view comes after the hackathon (PRD 4.7) |

Fixture stores live beside their screens (`src/account/store.ts`,
`src/report/reportFixture.ts`, `src/preview/teacherFixture.ts`,
`src/session/`) and are the only places sample data enters the app.

## Sign-in: sample build or Entra External ID

`src/auth/index.ts` fixes which sign-in a build uses, from its environment variables, never at run time and never by the browser:

| Build | When | Sign-in | Where the account lives |
|---|---|---|---|
| Sample (default) | `VITE_ENTRA_CLIENT_ID` or `VITE_ENTRA_AUTHORITY` is missing, or `VITE_ALO_ENV=local` | The fixture email-and-code sign-in the MVP screens run on | `localStorage`, sample data only |
| Real | Both Entra settings are present | **Microsoft Entra External ID**, one-time code emailed to the guardian, on Entra's hosted page (our screen passes the email as `loginHint`). The only method: the user flow should offer *Email one-time passcode* and not Google | **This tab only.** Nothing is written to the browser |

**Follow-up: typing the code on our own screen** (MSAL "native authentication", `@azure/msal-browser/custom-auth`) is not set up. Checked against the `aloaiauth` tenant on 2026-10-22: its native-auth endpoint answers `AADSTS550022` (the app registration is not enabled for native authentication) and sends no CORS headers, so it needs the app registration changed in the portal and a small same-origin proxy (for example a Static Web Apps managed Function under `/api/auth/*`), which is W1 infra.

Settings (all public values: the app is a public client with PKCE and holds no secret): `VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_AUTHORITY` (the tenant address WITH the tenant id: `https://<name>.ciamlogin.com/<tenant id>/`. Without the id MSAL fails with `endpoints_resolution_error` and sign-in never starts), optionally `VITE_ENTRA_API_SCOPE` (the Account API's scope, once it exists; `auth().getAccessToken()` then returns a bearer token).

**Fixture or live data** is chosen by the build alone (`src/api/mode.ts`). The build is *live* only when Entra sign-in is configured, `VITE_ALO_API_URL` (the Account API's address) is set, and `VITE_ALO_ENV` is not `local`. Then children, consent and reports go through the Account API (`src/api/`, with the Entra bearer token). Any other build is the *fixture* build: no network calls for account data. The browser, URL and user never choose. The teacher preview imports no data client in either build. In a live build the session runs over LiveKit (`src/session/liveDriver.ts`, data topic `aloai.session`, protocol v2) after `POST /v1/sessions` with `{child_id}`, which returns `{session_id, livekit_url, token}` (`schemas/session_start.schema.json`; that one call is in `src/session/driverFactory.ts`). The LiveKit client loads only when a live session starts and is not precached. The reports paths (`GET /v1/reports`, `/v1/reports/{session_id}`) are the Account API's (`services/account/reports.py`); change them in `src/report/useReports.ts` if the API does.

**Until the Account service exists, the real build keeps a guardian's children and consents in memory for the life of the tab and then they are gone.** That is deliberate: a child's first name and birth year must not stay in `localStorage` on a shared family phone (PRD 12). It also means the real build cannot yet be used for real families. The sign-in session itself is in `sessionStorage` (closed with the tab). A sample build's leftovers on the same origin are removed when the real build first loads.

The consent record's `sign_in_method` is `google`, `email_code` (the real build's emailed code) or `email_link` (the sample build only). The record's shape is `schemas/consent.schema.json`.

### Setting up Entra (by hand: an external tenant cannot be made by Terraform)

1. Create an **external** tenant (Entra admin center > Overview > Manage tenants > Create > External). Its sign-in address is `https://<name>.ciamlogin.com/`; add the tenant id to it (`https://<name>.ciamlogin.com/<tenant id>/`) and that is `VITE_ENTRA_AUTHORITY`.
2. **App registration** in that tenant: platform *Single-page application*, redirect URIs `infra/azure` output `web_redirect_uri` (and `http://localhost:5173/signin` for development). No client secret. Its application (client) id is `VITE_ENTRA_CLIENT_ID`.
3. **User flow** (Sign-up and sign-in): identity provider *Email one-time passcode* only (no Google), attribute *Email Address*. Add the app registration to it. The API app registration must expose the scope `access_as_user` and send `email` as an optional claim (the Account service needs it).
4. Set the `VITE_ENTRA_*` values and `VITE_ALO_API_URL` (the `account_url` output) as GitHub repository variables for the deploy workflow. `VITE_ENTRA_API_SCOPE` is required for a live build (`api://<API audience>/access_as_user`): without it no API call has a token. Also register the site's bare origin as a redirect URI if Entra refuses sign-out.

## Hosting: Azure Static Web Apps

`infra/azure/apps.tf` creates the Static Web Apps resource (Free tier, `westus2`: West Europe refused it, so the web app's static files, which hold no child data, are served from there; see the ADR exception). `public/staticwebapp.config.json` is its routing and headers: SPA fallback to `index.html`, long caching for hashed assets and none for `index.html` and the service worker, a Content-Security-Policy, and the microphone permission the child session needs. The workflow `.github/workflows/web-deploy-azure.yml` builds and deploys it (manual only; its header lists the variables it reads).

Not verified: the Content-Security-Policy and the routing were not run against Static Web Apps or a browser, and the deploy workflow has not run. If the policy blocks something, loosen it in `staticwebapp.config.json` and say why in the PR. `connect-src` allows `*.livekit.cloud` (https and wss), the Account API on `*.azurecontainerapps.io`, Entra, blob storage for the clips, and Google Fonts (the service worker fetches them). A custom domain or a self-hosted LiveKit would need this list and the Account `WEB_ORIGIN` changed.

The real build also ships the sign-in library (about 67 kB gzipped), which the service worker precaches for everyone on first visit.
