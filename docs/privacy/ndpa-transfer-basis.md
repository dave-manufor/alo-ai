# Cross-border transfer basis for the mini-study (NDPA 2023)

**Status:** W3 draft, 2026-10-22 (board item I2, #107). It records the team's position for the team-family mini-study only (PRD 13: 3 to 5 children, signed guardian consent). It is not legal advice: a qualified data-protection adviser checks it, with the DPIA, before the pilot (PRD 12).

## Why a transfer basis is needed

The children read in Nigeria and the services run in the EU (PRD 12, ADR 0001), so their personal data leaves Nigeria. The Nigeria Data Protection Act 2023 and the GAID 2025 directive restrict transfers abroad and treat anyone under 18 as a child, whose data needs a guardian's consent. The Act's part on cross-border transfers allows one when the recipient is bound by law, binding corporate rules, contract clauses or a code that give adequate protection, and otherwise on grounds such as the data subject's informed consent. The adviser confirms the exact sections that apply.

## Where the data goes

| Data | Where it is processed | Basis | For the study |
|---|---|---|---|
| Reading and answer audio, transcripts, word labels, scores, reports, plans, consent records, the child's profile (first name, class, birth year) | Azure, `swedencentral` (Cosmos DB, Blob Storage, Service Bus, Container Apps, AI Speech) | EU processing under the GDPR, with Microsoft's data protection addendum (standard contractual clauses) as the contract safeguard, plus the guardian's informed consent | Allowed |
| The live session's audio stream | The LiveKit server (E5, #85) | To be confirmed: where it runs and whether it keeps any media | **Gate** |
| The guardian's sign-in (email, Google identity) | The Entra External ID tenant (E6, #86) | Microsoft, as above, once the tenant's data location is confirmed | **Gate** |
| The built web app's files | Static Web Apps, `westus2` (the exception in ADR 0001) | No personal data in it; sign-in, children, consent and reports go to the Account API in the EU | Allowed |
| Any of a child's words sent to a language model (answers, retell, interest chat) | Google AI Studio's Gemini API, with a key (#150) | None: the key is not pinned to the EU and has no data processing agreement, and on a free tier it may train on inputs | **Not allowed.** Fictional data only |
| Email | Not used in the study (the Coach writes to the outbox) | n/a | n/a |

## The position

1. **The data in Azure `swedencentral` is covered** by EU processing plus Microsoft's addendum, together with the guardian's informed consent.
2. **No child data reaches a language model without an agreement.** Until Azure support clears the model block (715-123420, #83), or a paid provider with a data processing agreement and an EU option is chosen, the Gemini key processes fictional data only: rehearsals, the cloud smoke test, evaluation sets. A route that is chosen later is added to this table, named in the consent text, and its evaluation sets are rerun first (hard rule 6).
3. **Consent says it plainly** (I1, #106): the recordings are processed in the EU by Microsoft, kept for 90 days, and used only to produce the screening report. It names any other processor added later.

## Gates before a real child reads

- [ ] The consent text and the parent information sheet say what point 3 asks (I1, #106).
- [ ] Where the LiveKit server runs, and that it stores no media (E5, #85).
- [ ] The Entra tenant's data location (E6, #86).
- [ ] Children's audio is private and deleted after 90 days (I4, #109).
- [ ] No transcript or name appears in the logs (I7, #112).
- [ ] No child data reaches the Gemini key: the AI roles see fictional data only, or a covered route has replaced it.

## Before the pilot

The DPIA (PRD 12); the adviser's review of this note; whether the pilot needs a stronger check of the guardian than a verified email plus an attestation (PRD 12); and whether Alo.ai must register with the Nigeria Data Protection Commission.
