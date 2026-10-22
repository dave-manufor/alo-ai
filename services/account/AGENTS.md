# services/account: Account and Payments service (W1, reviewed by W2 or W3)

Consent records, children, `POST /v1/sessions` (LiveKit token + agent dispatch), `/internal/notify` email, Paystack checkout, webhooks and entitlements. Read PRD 4.4, 11, 12, 14.2 and the root `AGENTS.md` first.

- **Only this service holds the Paystack secret and the email key** (Secret Manager, env var injected by Terraform). Never log them and never move them to another service.
- Webhooks: verify `x-paystack-signature` (HMAC-SHA512) before anything else; a forged signature is rejected and a duplicate event changes nothing (idempotent). Tests required (13.5). Paystack stays in test mode.
- The microphone/session cannot start for a child without a consent record (text, version, timestamp, sign-in method, verified email). Check entitlement before creating a session.
- `POST /v1/sessions` (`sessions.py`, `rooms.py`) checks ownership, then consent, then makes the LiveKit room and token. The entitlement check is skipped while Paystack is later work (PRD changelog 2026-10-22); add it back there when payments land. Without `LIVEKIT_*` it answers 503.
- Guardians see only their own children. Every report read writes to `audit_log`.
- No agent may reach payment routes. No SMS, no phone numbers stored.
- **Produces:** `POST /v1/sessions` (W2), `/internal/notify` (W3 Coach), entitlements in `subscriptions/{guardian_id}` (W2). Contract changes: `alo-contract-change`.
- Emails never contain scores ("the report is ready" only).
