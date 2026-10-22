# services/reading_scorer: Reading Scorer (W3, reviewed by W2)

CPU-only Cloud Run service: two transcripts (Chirp 3 + Gemini), forced alignment (torchaudio MMS_FA), miscue labels, prosody phrasing, Phase 1 telemetry. Read PRD 5, 6.1-6.2, 10.2 and the root `AGENTS.md` first.

- No GPU. A word counts only when **both transcripts agree**; disagreements are `UNCERTAIN` and left out. Report the uncertain rate. **Exception: `SECOND_TRANSCRIPT=off`** (a server setting, Terraform only) scores from the first transcript alone when no second transcription model is available. Then W3's rule in `labels._label_single` applies: a right word counts from confidence 0.5, a different word is a `SUBSTITUTION` only from `SINGLE_SURE` (0.8, [CAL]), anything else, or a word with no confidence, is `UNCERTAIN`, and a transcript with no confidence at all scores nothing. The telemetry says `model_versions.transcripts = "single"` and carries the `SINGLE_TRANSCRIPT` flag, so the report is provisional. Rerun the golden recordings (L4) before trusting it.
- Raw audio goes to ASR; do not denoise unless an A/B shows a gain.
- Prosody phrasing is display-only and never feeds comprehension, level or profile. Expression is off.
- The scorer measures; it does not decide levels or profiles. Final numbers come from `libs/aloai/aloai_scoring.py`.
- Golden recordings: WCPM within +/-5 words and accuracy within +/-3 points. Keep tests deterministic with `AI_MODE=fixtures`.
- Scoring time target: report within 45 s of session end on Cloud Run's 2 vCPU. Bake the alignment model into the image.
- **Consumes:** passage artifact (W2, PRD 10.1), events from the Session Agent (W2). **Produces:** Phase 1 telemetry for the Grader. Contract changes: `alo-contract-change`.
- Never use real children's recordings in tests or commits.
