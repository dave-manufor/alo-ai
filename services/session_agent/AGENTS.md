# services/session_agent: Session Agent (W2, reviewed by W3)

LiveKit Agents worker on Cloud Run (CPU always allocated). Read PRD 3, 4.1-4.4, 5.1, 14.2 and the root `AGENTS.md` first.

- **The state machine decides every prompt and item** and is a pure function (state + event -> next state + actions). Gemini Live never skips, reorders or rewrites items. Keep it at 100% line coverage, including kindness/stop rules, both session profiles, both voice modes, reconnect/resume and fallbacks.
- "That word is X." is **always a clip** (4.2). Live may only use approved phrases for unscripted moments and never hints, rephrasings or judgement of answers.
- `VOICE_MODE` and `SESSION_PROFILE` come from server env (Terraform), never from the browser. Record the value used on the session record.
- Child audio is recorded per turn independently of Gemini Live and is the only input to grading. Audio objects are named by UUID v4.
- Fallback to scripted-clip mode if Live latency exceeds 2.5 s twice or errors (flag `LIVE_FALLBACK`).
- **Produces:** session protocol (data-channel commands, clip list) for W1; events `phase1.recorded` / `session.done` for W3. **Consumes:** `POST /v1/sessions` (W1), `grade:quick` (W3), entitlements (W1). Contract changes: use `alo-contract-change` and tag the consumer.
- Do not call the Grader's arithmetic yourself or compute scores here.
