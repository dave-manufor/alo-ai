# The values in use. Changing a server setting is a one-line pull request (chore/infra-...).
# After the demo: demo_warm = false and session_profile = "standard".
voice_mode      = "cache_first"
session_profile = "standard"
demo_warm       = false
agent_on        = false
coach_on        = true
generator_on    = false

# Images by digest, once CI has pushed them (until then the placeholder keeps the first apply working):
# images = {
#   session_agent  = "<acr>.azurecr.io/aloai-session-agent@sha256:..."
#   ...
# }

# budget_contact_emails has no default and is not set here: it is a person's address, so it
# comes from outside the repository (the TF_VAR_budget_contact_emails variable in CI, or
# -var on the command line). See README.md.

# ---- Models while Azure OpenAI is unavailable (2026-10-22)
# Every Azure OpenAI deployment is refused on this subscription (error 715-123420), so the model
# roles use Google's Gemini API through its OpenAI-compatible endpoint, and there are no Azure
# OpenAI deployments. The key is the Key Vault secret `llm-api-key`, created by hand first.
#
# DO NOT SCREEN REAL CHILDREN WITH THIS. A Google AI Studio key is not pinned to the EU and, on
# a free tier, may use inputs to improve Google's models. Use it with fictional data only until
# (1) a paid, agreement-covered route with EU processing is chosen and the parent information
# sheet names the provider, and (2) W3 has rerun the grading, tagger and Coach evaluation sets
# on these models (hard rule 6) and confirmed the single-transcript rule below (PRD 5.3).
# To go back: llm_base_url = "", llm_models = {} and restore openai_deployments.
llm_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
llm_models = {
  grader    = "gemini-3.1-flash-lite"
  quick     = "gemini-3.1-flash-lite"
  coach     = "gemini-3.1-flash-lite"
  generator = "gemini-3.1-flash-lite"
  tagger    = "gemini-3.1-flash-lite"
  embedding = "gemini-embedding-001"
}
openai_deployments = {}

# A generic session (David, 2026-10-22): no interest chat. Every session opens at the mic check
# with the bank passage for the child's level; nothing is chosen or generated from what they like.
interest_chat = false

# One transcript (Azure AI Speech): the Gemini endpoint has no /audio/transcriptions and a chat
# transcript dropped a word in a test. Needs W3's confirmation before real children (PRD 5.3).
second_transcript = "off"

# Entra External ID (the aloai external tenant; set up by hand, steps in ops/README.md). Identifiers only, no secrets.
entra_tenant_id    = "d611df49-f494-4953-9681-5a99d88b0d06"
entra_authority    = "https://aloaiauth.ciamlogin.com"
entra_api_audience = "15b55da5-38e0-4a9c-8b47-38f39e717bfe"
