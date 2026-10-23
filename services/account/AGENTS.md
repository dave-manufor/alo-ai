# services/account: Account and Payments service (W1, reviewed by W2 or W3)

Consent records, children, `POST /v1/sessions` (LiveKit token + agent dispatch), `/internal/notify` email, Paystack checkout, webhooks and entitlements. Read PRD 4.4, 11, 12, 14.2 and the root `AGENTS.md` first.

- **Only this service holds the Paystack secret and the email key** (Secret Manager, env var injected by Terraform). Never log them and never move them to another service.
- Webhooks: verify `x-paystack-signature` (HMAC-SHA512) before anything else; a forged signature is rejected and a duplicate event changes nothing (idempotent). Tests required (13.5). Paystack stays in test mode.
- The microphone/session cannot start for a child without a consent record (text, version, timestamp, sign-in method, verified email). Check entitlement before creating a session.
- `POST /v1/sessions` (`sessions.py`, `rooms.py`) checks ownership, then consent, then makes the LiveKit room and token. The entitlement check is skipped while Paystack is later work (PRD changelog 2026-10-22); add it back there when payments land. Without `LIVEKIT_*` it answers 503.
- `PATCH /v1/children/{child_id}` (`children.py`) changes only name, class and birth year, for the child's own guardian; consent is append-only and a changed choice is a new consent. There is no delete route: deletion is `ops/delete_child.py`, run by the study team.
- `GET /v1/sessions/{session_id}` (`sessions.py`) tells the guardian who started a session where it has got to (`PENDING|STARTED|COMPLETE|INCOMPLETE`, `report_ready`, `plan_ready`); it reads `session_starts/{id}` (written by `POST /v1/sessions`) for ownership, so another guardian's session is a 404.
- `GET /v1/plans/{session_id}` (`plans.py`) returns the Coach's plan, trimmed (`schemas/guardian_plan.schema.json`: no guardian id, no audio path), with its books and their licence and attribution. No subscription check while Paystack is later work; it makes no number.
- `GET /v1/reports` and `/v1/reports/{session_id}` (`reports.py`) only read what the Grader and Coach wrote, for the guardian named on the report; someone else's report is a 404. They make and change no number.
- Guardians see only their own children. Every report read writes to `audit_log`.
- No agent may reach payment routes. No SMS, no phone numbers stored.
- **Produces:** `POST /v1/sessions` (W2), `/internal/notify` (W3 Coach), entitlements in `subscriptions/{guardian_id}` (W2). Contract changes: `alo-contract-change`.
- Emails never contain scores ("the report is ready" only).
