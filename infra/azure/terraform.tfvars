# The values in use. Changing a server setting is a one-line pull request (chore/infra-...).
# After the demo: demo_warm = false and session_profile = "standard".
voice_mode      = "cache_first"
session_profile = "standard"
demo_warm       = false
agent_on        = false
coach_on        = true

# Images by digest, once CI has pushed them (until then the placeholder keeps the first apply working):
# images = {
#   session_agent  = "<acr>.azurecr.io/aloai-session-agent@sha256:..."
#   ...
# }

# budget_contact_emails has no default and is not set here: it is a person's address, so it
# comes from outside the repository (the TF_VAR_budget_contact_emails variable in CI, or
# -var on the command line). See README.md.
