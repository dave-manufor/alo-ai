# The four services and the book-ingestion job, on Container Apps (Consumption plan). Scale
# to zero unless something breaks without a warm instance (PRD 14.5): demo_warm and agent_on
# set the minimums. Environment variables are the ones docs/LOCAL_DEV.md lists.

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.prefix}-logs"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_container_app_environment" "main" {
  name                       = "${var.prefix}-env"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = var.tags
}

locals {
  deployment_names = { for role, _ in var.openai_deployments : role => "${var.prefix}-${role}" }

  # Another provider (var.llm_base_url) for the model roles: its model names replace the Azure
  # deployment names, and its key comes from the Key Vault secret llm-api-key.
  llm_on      = var.llm_base_url != ""
  model_names = local.llm_on ? merge(local.deployment_names, var.llm_models) : local.deployment_names

  # what every service reads to reach the data layer
  base_env = {
    CLOUD                      = "azure"
    AI_MODE                    = "live"
    AZURE_COSMOS_ENDPOINT      = azurerm_cosmosdb_account.main.endpoint
    AZURE_COSMOS_DATABASE      = azurerm_cosmosdb_sql_database.main.name
    AZURE_SERVICEBUS_NAMESPACE = azurerm_servicebus_namespace.main.name
    AZURE_STORAGE_ACCOUNT      = azurerm_storage_account.main.name
    EVENT_ROUTES               = jsonencode(local.events)
    AUDIO_BUCKET               = azurerm_storage_container.audio.name
    CLIPS_BUCKET               = azurerm_storage_container.clips.name
  }

  # what a service reads to reach Azure OpenAI and Speech
  ai_env = {
    AZURE_OPENAI_ENDPOINT    = azurerm_cognitive_account.openai.endpoint
    AZURE_OPENAI_DEPLOYMENTS = jsonencode(local.model_names)
    LLM_BASE_URL             = var.llm_base_url
    AZURE_SPEECH_REGION      = azurerm_cognitive_account.speech.location
    AZURE_SPEECH_RESOURCE_ID = azurerm_cognitive_account.speech.id
    AZURE_SPEECH_LOCALE      = var.speech_locale
  }

  # One local per app, not one map of all of them: the apps point at each other (the Session
  # Agent at Core, Core at the Account service), and one map would make every app depend on all.
  # AZURE_CLIENT_ID picks the app's own managed identity for DefaultAzureCredential.
  env_account = merge(local.base_env, {
    WEB_ORIGIN      = "https://${azurerm_static_web_app.web.default_host_name}" # the only origin allowed to call it (CORS)
    LIVEKIT_URL     = var.livekit_url
    AZURE_CLIENT_ID = azurerm_user_assigned_identity.svc["account"].client_id
  })

  env_core = merge(local.base_env, local.ai_env, {
    EVENT_QUEUE     = "core-events"
    COACH_ON        = tostring(var.coach_on)
    GENERATOR_ON    = tostring(var.generator_on)
    TTS_VOICE       = var.tts_voice
    ACCOUNT_URL     = "https://${azurerm_container_app.account.ingress[0].fqdn}"
    AZURE_CLIENT_ID = azurerm_user_assigned_identity.svc["core"].client_id
  })

  env_session_agent = merge(local.base_env, {
    AZURE_SPEECH_REGION      = local.ai_env.AZURE_SPEECH_REGION
    AZURE_SPEECH_RESOURCE_ID = local.ai_env.AZURE_SPEECH_RESOURCE_ID
    AZURE_SPEECH_LOCALE      = var.speech_locale
    GENERATOR_ON             = tostring(var.generator_on)
    AZURE_OPENAI_ENDPOINT    = local.ai_env.AZURE_OPENAI_ENDPOINT # the tagger
    AZURE_OPENAI_DEPLOYMENTS = local.ai_env.AZURE_OPENAI_DEPLOYMENTS
    LLM_BASE_URL             = local.ai_env.LLM_BASE_URL
    INTEREST_CHAT            = tostring(var.interest_chat)
    VOICE_MODE               = var.voice_mode
    SESSION_PROFILE          = var.session_profile
    VOICE_PROFILE_ID         = var.voice_profile_id
    CLIPS_BASE_URL           = "${azurerm_storage_account.main.primary_blob_endpoint}${azurerm_storage_container.clips.name}"
    CORE_URL                 = "https://${azurerm_container_app.core.ingress[0].fqdn}"
    LIVEKIT_URL              = var.livekit_url
    AZURE_CLIENT_ID          = azurerm_user_assigned_identity.svc["session-agent"].client_id
  })

  env_reading_scorer = merge(local.base_env, local.ai_env, {
    EVENT_QUEUE       = "scorer-events"
    AZURE_CLIENT_ID   = azurerm_user_assigned_identity.svc["reading-scorer"].client_id
    SECOND_TRANSCRIPT = var.second_transcript
    # It calls no model in single-transcript mode and has no provider key, and aloai_env refuses
    # an address without a key.
    LLM_BASE_URL = ""
  })

  env_book_ingest = merge(local.base_env, local.ai_env, {
    BOOKS_BUCKET    = azurerm_storage_container.books.name
    AZURE_CLIENT_ID = azurerm_user_assigned_identity.svc["ingest"].client_id
  })

  warm = var.demo_warm
}

# ---- Session Agent: the LiveKit worker. It dials out to LiveKit, so it has no ingress.

resource "azurerm_container_app" "session_agent" {
  lifecycle {
    # Azure fills in "Consumption"; the provider would otherwise blank it on every plan.
    ignore_changes = [workload_profile_name]
  }

  name                         = "${var.prefix}-session-agent"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.svc["session-agent"].id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.svc["session-agent"].id
  }

  secret {
    name                = "livekit-api-key"
    identity            = azurerm_user_assigned_identity.svc["session-agent"].id
    key_vault_secret_id = local.secret_uri["livekit-api-key"]
  }

  secret {
    name                = "livekit-api-secret"
    identity            = azurerm_user_assigned_identity.svc["session-agent"].id
    key_vault_secret_id = local.secret_uri["livekit-api-secret"]
  }

  dynamic "secret" {
    for_each = local.llm_on ? ["llm-api-key"] : []
    content {
      name                = secret.value
      identity            = azurerm_user_assigned_identity.svc["session-agent"].id
      key_vault_secret_id = local.secret_uri[secret.value]
    }
  }

  template {
    min_replicas = var.agent_on || local.warm ? 1 : 0
    max_replicas = 2

    container {
      name   = "session-agent"
      image  = var.images["session_agent"]
      cpu    = 1
      memory = "2Gi"

      dynamic "env" {
        for_each = local.env_session_agent
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name        = "LIVEKIT_API_KEY"
        secret_name = "livekit-api-key"
      }

      env {
        name        = "LIVEKIT_API_SECRET"
        secret_name = "livekit-api-secret"
      }

      dynamic "env" {
        for_each = local.llm_on ? ["llm-api-key"] : []
        content {
          name        = "LLM_API_KEY"
          secret_name = env.value
        }
      }
    }
  }

  depends_on = [azurerm_role_assignment.rbac, azurerm_cosmosdb_sql_role_assignment.data]
}

# ---- Core: the quick grade endpoint (internal, the Session Agent calls it), and the events from
# core-events. The queue rule wakes it from zero when an event arrives.

resource "azurerm_container_app" "core" {
  lifecycle {
    ignore_changes = [workload_profile_name]
  }

  name                         = "${var.prefix}-core"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.svc["core"].id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.svc["core"].id
  }

  dynamic "secret" {
    for_each = local.llm_on ? ["llm-api-key"] : []
    content {
      name                = secret.value
      identity            = azurerm_user_assigned_identity.svc["core"].id
      key_vault_secret_id = local.secret_uri[secret.value]
    }
  }

  ingress {
    external_enabled = false
    target_port      = 8080

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = local.warm ? 1 : 0
    max_replicas = 2

    http_scale_rule {
      name                = "http"
      concurrent_requests = "10"
    }

    custom_scale_rule {
      name             = "core-events"
      custom_rule_type = "azure-servicebus"
      identity_id      = azurerm_user_assigned_identity.svc["core"].id
      metadata = {
        queueName    = "core-events"
        namespace    = azurerm_servicebus_namespace.main.name
        messageCount = "1"
      }
    }

    container {
      name   = "core"
      image  = var.images["core"]
      cpu    = 1
      memory = "2Gi"

      dynamic "env" {
        for_each = local.env_core
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.llm_on ? ["llm-api-key"] : []
        content {
          name        = "LLM_API_KEY"
          secret_name = env.value
        }
      }
    }
  }

  depends_on = [azurerm_role_assignment.rbac, azurerm_cosmosdb_sql_role_assignment.data]
}

# ---- Reading Scorer: CPU only, 2 vCPU and 4 GiB (PRD 5.3). Events only: no ingress.

resource "azurerm_container_app" "reading_scorer" {
  lifecycle {
    ignore_changes = [workload_profile_name]
  }

  name                         = "${var.prefix}-reading-scorer"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.svc["reading-scorer"].id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.svc["reading-scorer"].id
  }

  template {
    min_replicas = local.warm ? 1 : 0
    max_replicas = 2

    custom_scale_rule {
      name             = "scorer-events"
      custom_rule_type = "azure-servicebus"
      identity_id      = azurerm_user_assigned_identity.svc["reading-scorer"].id
      metadata = {
        queueName    = "scorer-events"
        namespace    = azurerm_servicebus_namespace.main.name
        messageCount = "1"
      }
    }

    container {
      name   = "reading-scorer"
      image  = var.images["reading_scorer"]
      cpu    = 2
      memory = "4Gi"

      dynamic "env" {
        for_each = local.env_reading_scorer
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  depends_on = [azurerm_role_assignment.rbac, azurerm_cosmosdb_sql_role_assignment.data]
}

# ---- Account and Payments: the only holder of the Paystack secret and the email key. External:
# the web app, the Paystack webhooks and the LiveKit token requests reach it.

resource "azurerm_container_app" "account" {
  lifecycle {
    ignore_changes = [workload_profile_name]
  }

  name                         = "${var.prefix}-account"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.svc["account"].id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.svc["account"].id
  }

  dynamic "secret" {
    # Not the model provider's key: the Account service calls no model and has no role on it.
    for_each = setsubtract(local.secrets, ["llm-api-key"])
    content {
      name                = secret.value
      identity            = azurerm_user_assigned_identity.svc["account"].id
      key_vault_secret_id = local.secret_uri[secret.value]
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8080

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = local.warm ? 1 : 0
    max_replicas = 2

    container {
      name   = "account"
      image  = var.images["account"]
      cpu    = 0.5
      memory = "1Gi"

      dynamic "env" {
        for_each = local.env_account
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name        = "PAYSTACK_SECRET_KEY"
        secret_name = "paystack-secret-key"
      }

      env {
        name        = "RESEND_API_KEY"
        secret_name = "resend-api-key"
      }

      env {
        name        = "LIVEKIT_API_KEY"
        secret_name = "livekit-api-key"
      }

      env {
        name        = "LIVEKIT_API_SECRET"
        secret_name = "livekit-api-secret"
      }
    }
  }

  depends_on = [azurerm_role_assignment.rbac, azurerm_cosmosdb_sql_role_assignment.data]
}

# ---- Book ingestion: built from the Core image (PRD 9.1), run by hand when the catalogue changes.

resource "azurerm_container_app_job" "book_ingest" {
  lifecycle {
    ignore_changes = [workload_profile_name]
  }

  name                         = "${var.prefix}-book-ingest"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  container_app_environment_id = azurerm_container_app_environment.main.id
  replica_timeout_in_seconds   = 1800
  replica_retry_limit          = 0
  tags                         = var.tags

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.svc["ingest"].id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.svc["ingest"].id
  }

  dynamic "secret" {
    for_each = local.llm_on ? ["llm-api-key"] : []
    content {
      name                = secret.value
      identity            = azurerm_user_assigned_identity.svc["ingest"].id
      key_vault_secret_id = local.secret_uri[secret.value]
    }
  }

  template {
    container {
      name   = "book-ingest"
      image  = var.images["book_ingest"]
      cpu    = 1
      memory = "2Gi"
      # Without a command the Core image would start its web server and run until the timeout.
      # Until the ingestion job exists, this embeds the catalogue with the Azure model
      # (services/core/books/reembed.py).
      command = ["python", "-m", "services.core.books.reembed"]

      dynamic "env" {
        for_each = local.env_book_ingest
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.llm_on ? ["llm-api-key"] : []
        content {
          name        = "LLM_API_KEY"
          secret_name = env.value
        }
      }
    }
  }

  depends_on = [azurerm_role_assignment.rbac, azurerm_cosmosdb_sql_role_assignment.data]
}

# ---- the web app (PWA): Static Web Apps, Free tier. CI builds it and deploys with a token it
# reads at run time (`az staticwebapp secrets list`), so no deployment token is in state.

resource "azurerm_static_web_app" "web" {
  name                = "${var.prefix}-web"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.web_location
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = var.tags
}

# ---- Seed: the clips and the bank passages (services/session_agent/seed.py), run by hand
# after an apply and whenever VOICE_PROFILE_ID or the passages change. It runs as the Session
# Agent's own identity, which already may write the clips container and the documents and call
# Speech, so it needs no roles of its own. Clips already there are never replaced.

resource "azurerm_container_app_job" "seed" {
  lifecycle {
    ignore_changes = [workload_profile_name]
  }

  name                         = "${var.prefix}-seed"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  container_app_environment_id = azurerm_container_app_environment.main.id
  replica_timeout_in_seconds   = 1800
  replica_retry_limit          = 0
  tags                         = var.tags

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.svc["session-agent"].id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.svc["session-agent"].id
  }

  template {
    container {
      name    = "seed"
      image   = var.images["session_agent"]
      cpu     = 1
      memory  = "2Gi"
      command = ["python", "-m", "services.session_agent.seed"]

      dynamic "env" {
        # The seed only makes speech clips: no model, so no provider address (it has no key).
        for_each = merge(local.env_session_agent, { TTS_VOICE = var.tts_voice, LLM_BASE_URL = "" })
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  depends_on = [azurerm_role_assignment.rbac, azurerm_cosmosdb_sql_role_assignment.data]
}
