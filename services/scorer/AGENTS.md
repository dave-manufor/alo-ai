# services/scorer: Reading Scorer (W3, reviewed by W2)

CPU-only Cloud Run service: two transcripts (Chirp 3 + Gemini), forced alignment (torchaudio MMS_FA), miscue labels, prosody phrasing, Phase 1 telemetry. Read PRD 5, 6.1-6.2, 10.2 and the root `AGENTS.md` first.

- No GPU. A word counts only when **both transcripts agree**; disagreements are `UNCERTAIN` and left out. Report the uncertain rate.
- Raw audio goes to ASR; do not denoise unless an A/B shows a gain.
- Prosody phrasing is display-only and never feeds comprehension, level or profile. Expression is off.
- The scorer measures; it does not decide levels or profiles. Final numbers come from `libs/aloai_scoring.py`.
- Golden recordings: WCPM within +/-5 words and accuracy within +/-3 points. Keep tests deterministic with `AI_MODE=fixtures`.
- Scoring time target: report within 45 s of session end on Cloud Run's 2 vCPU. Bake the alignment model into the image.
- **Consumes:** passage artifact (W2, PRD 10.1), events from the Session Agent (W2). **Produces:** Phase 1 telemetry for the Grader. Contract changes: `alo-contract-change`.
- Never use real children's recordings in tests or commits.
