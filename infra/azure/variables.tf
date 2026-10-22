variable "location" {
  description = "Azure region for everything. EU only (hard rule 9)."
  type        = string
  default     = "swedencentral"
  validation {
    condition     = contains(["swedencentral", "northeurope", "westeurope", "francecentral", "germanywestcentral", "norwayeast", "polandcentral", "italynorth", "spaincentral"], var.location)
    error_message = "location must be an EU or EEA region."
  }
}

variable "prefix" {
  description = "Name prefix for every resource."
  type        = string
  default     = "aloai"
}

variable "tags" {
  type = map(string)
  default = {
    project = "aloai"
    env     = "dev"
  }
}

variable "github_owner_id" {
  description = "The numeric id of the GitHub account that owns the repository (gh api users/<owner> --jq .id). It is part of the OIDC subject GitHub presents."
  type        = string
  default     = "107783499"
}

variable "github_repository_id" {
  description = "The numeric id of the repository (gh api repos/<owner>/<name> --jq .id). It is part of the OIDC subject GitHub presents."
  type        = string
  default     = "1421059333"
}

variable "github_repository" {
  description = "owner/name of the repository whose main branch CI deploys from (OIDC, no keys)."
  type        = string
  default     = "dave-manufor/alo-ai"
}

# ---- server settings (PRD 4.1, 4.2, 14.5): changed only by a one-line chore/infra-... PR

variable "voice_mode" {
  type    = string
  default = "cache_first"
  validation {
    condition     = contains(["cache_first", "live_first"], var.voice_mode)
    error_message = "voice_mode must be cache_first or live_first."
  }
}

variable "session_profile" {
  type    = string
  default = "standard"
  validation {
    condition     = contains(["standard", "demo"], var.session_profile)
    error_message = "session_profile must be standard or demo."
  }
}

variable "demo_warm" {
  description = "Minimum 1 replica on all four services, from the evening before the demo."
  type        = bool
  default     = false
}

variable "agent_on" {
  description = "Session Agent minimum 1 replica (from day 3): the LiveKit worker must be running to take a session."
  type        = bool
  default     = false
}

variable "llm_base_url" {
  description = "An OpenAI-compatible provider used for the model roles instead of Azure OpenAI deployments, or \"\" for Azure OpenAI. The provider's API key is the Key Vault secret `llm-api-key`, created by hand (`az keyvault secret set`) before the apply that sets this. Sending data to a provider needs a data-processing agreement and W3's evaluation first (see the comment in terraform.tfvars)."
  type        = string
  default     = ""
  validation {
    condition     = var.llm_base_url == "" || startswith(var.llm_base_url, "https://")
    error_message = "llm_base_url must be empty or an https:// address."
  }
}

variable "llm_models" {
  description = "Role -> the provider's model name (grader, quick, coach, generator, tagger, embedding, transcribe). Used with llm_base_url; a role not named here keeps its Azure deployment name."
  type        = map(string)
  default     = {}
}

variable "interest_chat" {
  description = "false: a generic session. No interest chat; every session opens at the mic check with the bank passage chosen by the child's level, never by what they like. true: the session opens by asking what the child likes (PRD 4)."
  type        = bool
  default     = true
}

variable "second_transcript" {
  description = "\"on\": a word counts only where two transcripts agree (PRD 5.3). \"off\": the Reading Scorer scores from the Azure AI Speech transcript alone, which needs no OpenAI transcription deployment but relaxes that rule: leave it on unless W3 has confirmed the single-transcript rule and rerun the golden recordings."
  type        = string
  default     = "on"
  validation {
    condition     = contains(["on", "off"], var.second_transcript)
    error_message = "second_transcript must be \"on\" or \"off\"."
  }
}

variable "coach_on" {
  description = "false turns the Reading Coach off: every plan is the template plan."
  type        = bool
  default     = true
}

variable "generator_on" {
  description = "Lets plan.ready pre-generate a child's next story and the Session Agent ask the Passage Generator for the story. false: every session reads a bank passage. Stays false until the Writer + Critic and tagger evaluation sets pass on the Azure deployments, and until word clips are made for generated stories (G5)."
  type        = bool
  default     = false
}

# ---- images: CI builds and pushes them; Terraform receives only each image's digest

variable "images" {
  description = "Container image for each app, by digest, e.g. aloaiacr.azurecr.io/aloai-core@sha256:... Until CI has pushed one, the quickstart placeholder keeps the first apply working."
  type        = map(string)
  default = {
    session_agent  = "mcr.microsoft.com/k8se/quickstart:latest"
    account        = "mcr.microsoft.com/k8se/quickstart:latest"
    reading_scorer = "mcr.microsoft.com/k8se/quickstart:latest"
    core           = "mcr.microsoft.com/k8se/quickstart:latest"
    book_ingest    = "mcr.microsoft.com/k8se/quickstart:latest"
  }
  validation {
    condition     = alltrue([for k in ["session_agent", "account", "reading_scorer", "core", "book_ingest"] : contains(keys(var.images), k)])
    error_message = "images needs session_agent, account, reading_scorer, core and book_ingest."
  }
}

# ---- voice and speech

variable "voice_profile_id" {
  description = "Names the Azure voice's clips in the clip store, apart from the Google ones."
  type        = string
  default     = "vp_azure_v1"
}

variable "tts_voice" {
  description = "Azure neural voice for Auntie Kemi and the parent summary."
  type        = string
  default     = "en-NG-EzinneNeural"
}

variable "speech_locale" {
  description = "Recognition locale (PRD 5.2): en-GB until the day-1 check says otherwise."
  type        = string
  default     = "en-GB"
}

variable "livekit_url" {
  description = "wss:// URL of the LiveKit server (configured outside Terraform; its key and secret are Key Vault secrets)."
  type        = string
  default     = "wss://livekit.invalid"
}

variable "web_origins" {
  description = "Origins of the web app, allowed to fetch clips (CORS)."
  type        = list(string)
  default     = ["http://localhost:5173"]
}

# ---- Azure OpenAI: one deployment per role the services name in AZURE_OPENAI_DEPLOYMENTS

variable "openai_deployments" {
  description = "Deployments by role. sku must keep processing in the EU: DataZoneStandard (EU data zone) or Standard (regional). GlobalStandard may process outside the EU, which hard rule 9 and the NDPA transfer basis do not allow. Check model availability in the region first."
  type = map(object({
    model    = string
    version  = string
    sku      = string
    capacity = number
  }))
  default = {
    # REVISIT: the chat roles were gpt-4.1 / gpt-4.1-mini on DataZoneStandard, but this subscription
    # has no quota for them (2026-10-22), so they run on the regional Standard gpt-4o it does have
    # (50 in all, split below; gpt-4o-mini 2024-07-18 is refused as deprecated). A model change
    # needs the evaluation sets rerun (hard rule 6, alo-prompt-eval) before a real child is
    # screened; revisit when gpt-4.1 quota is granted.
    grader     = { model = "gpt-4o", version = "2024-11-20", sku = "Standard", capacity = 20 }
    quick      = { model = "gpt-4o", version = "2024-11-20", sku = "Standard", capacity = 10 }
    coach      = { model = "gpt-4o", version = "2024-11-20", sku = "Standard", capacity = 8 }
    embedding  = { model = "text-embedding-3-small", version = "1", sku = "DataZoneStandard", capacity = 50 }
    transcribe = { model = "gpt-4o-transcribe", version = "2025-03-20", sku = "DataZoneStandard", capacity = 30 }
    generator  = { model = "gpt-4o", version = "2024-11-20", sku = "Standard", capacity = 8 }
    tagger     = { model = "gpt-4o", version = "2024-11-20", sku = "Standard", capacity = 4 }
  }
  validation {
    condition     = alltrue([for d in values(var.openai_deployments) : contains(["Standard", "DataZoneStandard"], d.sku)])
    error_message = "sku must be Standard or DataZoneStandard so processing stays in the EU."
  }
}

# ---- budget: US$150 of Azure credit

variable "budget_amount" {
  type    = number
  default = 150
}

variable "budget_alerts" {
  description = "Spend in US$ at which the budget emails the contacts."
  type        = list(number)
  default     = [50, 100, 130]
}

variable "budget_contact_emails" {
  description = "Who the budget alerts email. Required, and not in terraform.tfvars: it is a person's address, so it comes from outside the repository (TF_VAR_budget_contact_emails in CI)."
  type        = list(string)
  validation {
    condition     = length(var.budget_contact_emails) > 0
    error_message = "budget_contact_emails must name at least one person, or the alerts reach nobody."
  }
}

variable "budget_start" {
  description = "First day of a month, RFC 3339."
  type        = string
  default     = "2026-10-01T00:00:00Z"
}

variable "web_location" {
  description = "Region for the Static Web Apps resource. It is offered in few regions and West Europe, the EU one, was not accepting new customers on 2026-10-22, so the default is West US 2. Only the site configuration lives there: the pages are served from Azure's edge, the app holds no child data, and reports come from the Account API in the EU. Move back to westeurope when it reopens."
  type        = string
  default     = "westus2"
  validation {
    condition     = contains(["westeurope", "westus2", "eastus2"], var.web_location)
    error_message = "web_location must be westeurope, westus2 or eastus2 (the regions Static Web Apps is offered in that this project accepts)."
  }
}

variable "entra_tenant_id" {
  description = "The Entra External ID (external) tenant id. Not a secret; the Account service checks the token tid and issuer with it."
  type        = string
  default     = ""
}

variable "entra_authority" {
  description = "The external tenant sign-in address, such as https://aloaiauth.ciamlogin.com (no path)."
  type        = string
  default     = ""
}

variable "entra_api_audience" {
  description = "The Account API app registration application (client) id: the token aud."
  type        = string
  default     = ""
}
