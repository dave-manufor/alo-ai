# Alo.ai on Azure (CLOUD=azure): one flat configuration, no modules. The Google Cloud
# equivalent is described in PRD 15.1; the service map is in docs/adr/0001-azure-as-a-second-cloud.md.
#
# Nothing here uses a key or a connection string: every service reaches Cosmos DB, Service Bus,
# Blob Storage, Azure OpenAI, Speech and Key Vault with its own managed identity, and the
# accounts have local (key) authentication turned off. Secret VALUES are never in Terraform
# or its state (README.md).

data "azurerm_client_config" "current" {}

locals {
  # Names that must be unique across Azure get a stable suffix from the subscription.
  suffix = substr(sha1(data.azurerm_client_config.current.subscription_id), 0, 6)

  services = toset(["session-agent", "account", "reading-scorer", "core", "ingest"])

  events = jsondecode(file("${path.module}/../events.json")).queues # queue -> event types, the one table the code reads too
  queues = toset(keys(local.events))

  # Built-in role definition used for Cosmos DB's data plane (it is not an Azure RBAC role).
  cosmos_data_contributor = "${azurerm_cosmosdb_account.main.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
}

resource "azurerm_resource_group" "main" {
  name     = "${var.prefix}-rg"
  location = var.location
  tags     = var.tags
}

# ---- identity: one managed identity per service (hard rule 9), and one for CI

resource "azurerm_user_assigned_identity" "svc" {
  for_each            = local.services
  name                = "${var.prefix}-${each.key}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "ci" {
  name                = "${var.prefix}-ci-deployer"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = var.tags
}

# CI signs in with GitHub's OIDC token: no key files. Only main deploys.
resource "azurerm_federated_identity_credential" "ci_main" {
  name                = "github-main"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.ci.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_repository}:ref:refs/heads/main"
}

# ---- registry

resource "azurerm_container_registry" "main" {
  name                = "${var.prefix}acr${local.suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

# ---- storage: audio (private, 90-day lifecycle, PRD 12), clips (public read), books

resource "azurerm_storage_account" "main" {
  name                            = "${var.prefix}store${local.suffix}"
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  # Only the clips container is public: the browser fetches the clips by URL (CLIPS_BASE_URL).
  # audio and books stay private.
  allow_nested_items_to_be_public = true
  tags                            = var.tags

  blob_properties {
    cors_rule {
      allowed_headers    = ["*"]
      allowed_methods    = ["GET", "HEAD"]
      allowed_origins    = concat(var.web_origins, ["https://${azurerm_static_web_app.web.default_host_name}"])
      exposed_headers    = ["*"]
      max_age_in_seconds = 3600
    }
  }
}

resource "azurerm_storage_container" "audio" {
  name                  = "audio"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "clips" {
  name                  = "clips"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "blob"
}

resource "azurerm_storage_container" "books" {
  name                  = "books"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

# Child audio: cooler after 30 days, deleted after 90 (PRD 12).
resource "azurerm_storage_management_policy" "audio" {
  storage_account_id = azurerm_storage_account.main.id

  rule {
    name    = "audio-lifecycle"
    enabled = true
    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["audio/"]
    }
    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than = 30
        delete_after_days_since_modification_greater_than       = 90
      }
    }
  }
}

# ---- Cosmos DB: Firestore's counterpart (free tier: 1000 RU/s and 25 GB, one per subscription)

resource "azurerm_cosmosdb_account" "main" {
  name                         = "${var.prefix}-cosmos-${local.suffix}"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  offer_type                   = "Standard"
  kind                         = "GlobalDocumentDB"
  free_tier_enabled            = true
  local_authentication_enabled = false
  minimal_tls_version          = "Tls12"
  tags                         = var.tags

  capabilities {
    name = "EnableNoSQLVectorSearch"
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.main.location
    failover_priority = 0
  }
}

# Throughput is shared by the database's containers, so it stays inside the free 1000 RU/s.
resource "azurerm_cosmosdb_sql_database" "main" {
  name                = "aloai"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  throughput          = 1000
}

# Every document: {id, pk, col, d} (libs/aloai/aloai_store.CosmosStore); pk is the top-level document.
resource "azurerm_cosmosdb_sql_container" "docs" {
  name                = "docs"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/pk"]
}

# The catalogue, with the vector index the Grader's book search uses (services/core/grader/azure.py).
# azurerm has no vector policy yet, so this one container is made through azapi. 768 numbers per
# book: book.schema.json. quantizedFlat suits a catalogue of tens of books (diskANN wants thousands).
resource "azapi_resource" "books" {
  type      = "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15"
  name      = "books"
  parent_id = azurerm_cosmosdb_sql_database.main.id

  body = {
    properties = {
      resource = {
        id           = "books"
        partitionKey = { paths = ["/pk"], kind = "Hash" }
        vectorEmbeddingPolicy = {
          vectorEmbeddings = [{
            path             = "/d/embedding"
            dataType         = "float32"
            dimensions       = 768
            distanceFunction = "cosine"
          }]
        }
        indexingPolicy = {
          indexingMode  = "consistent"
          automatic     = true
          includedPaths = [{ path = "/*" }]
          excludedPaths = [{ path = "/d/embedding/*" }, { path = "/\"_etag\"/?" }]
          vectorIndexes = [{ path = "/d/embedding", type = "quantizedFlat" }]
        }
      }
    }
  }
}

# ---- Service Bus: Pub/Sub's counterpart. A queue for each service that handles events
# (infra/events.json). Basic tier: queues only, and no duplicate detection (consumers drop
# repeats by event_id). Five deliveries, then the dead-letter queue, as Pub/Sub does.

resource "azurerm_servicebus_namespace" "main" {
  name                = "${var.prefix}-bus-${local.suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  local_auth_enabled  = false
  minimum_tls_version = "1.2"
  tags                = var.tags
}

resource "azurerm_servicebus_queue" "events" {
  for_each     = local.queues
  name         = each.key
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count  = 5
  lock_duration       = "PT5M" # the pump renews it up to 10 minutes while grading runs
  default_message_ttl = "P1D"
}

# ---- Key Vault: the entries and who may read them. The VALUES are set outside Terraform
# (README.md); the placeholder below is not a secret, and a later value is never overwritten.

resource "azurerm_key_vault" "main" {
  name                       = "${var.prefix}-kv-${local.suffix}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = false
  soft_delete_retention_days = 7
  tags                       = var.tags
}

locals {
  secrets = toset(["paystack-secret-key", "resend-api-key", "livekit-api-key", "livekit-api-secret"])
}

resource "azurerm_key_vault_secret" "entry" {
  for_each     = local.secrets
  name         = each.key
  key_vault_id = azurerm_key_vault.main.id
  value        = "set-outside-terraform"
  content_type = "placeholder until `az keyvault secret set`"

  lifecycle {
    ignore_changes = [value, content_type]
  }

  depends_on = [azurerm_role_assignment.ci]
}

# ---- Azure AI: OpenAI and Speech. Entra only (no keys); a custom subdomain is needed for that.

resource "azurerm_cognitive_account" "openai" {
  name                          = "${var.prefix}-openai-${local.suffix}"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = "${var.prefix}-openai-${local.suffix}"
  local_auth_enabled            = false
  public_network_access_enabled = true
  tags                          = var.tags
}

resource "azurerm_cognitive_deployment" "openai" {
  for_each             = var.openai_deployments
  name                 = "${var.prefix}-${each.key}"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = each.value.model
    version = each.value.version
  }

  sku {
    name     = each.value.sku
    capacity = each.value.capacity
  }
}

resource "azurerm_cognitive_account" "speech" {
  name                          = "${var.prefix}-speech-${local.suffix}"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  kind                          = "SpeechServices"
  sku_name                      = "S0"
  custom_subdomain_name         = "${var.prefix}-speech-${local.suffix}"
  local_auth_enabled            = false
  public_network_access_enabled = true
  tags                          = var.tags
}

# ---- access: least privilege. Each line is who may do what, where.

locals {
  id = { for name, identity in azurerm_user_assigned_identity.svc : name => identity.principal_id }

  queue_id = { for name, queue in azurerm_servicebus_queue.events : name => queue.id }

  # CI: push images, deploy the apps, and manage what Terraform manages (roles included).
  # Kept apart from the rest because the Key Vault entries need CI's role before they exist,
  # and the roles below need the entries.
  rbac_ci = {
    "ci-acrpush"          = { scope = azurerm_container_registry.main.id, role = "AcrPush" }
    "ci-contributor"      = { scope = azurerm_resource_group.main.id, role = "Contributor" }
    "ci-rbac-admin"       = { scope = azurerm_resource_group.main.id, role = "Role Based Access Control Administrator" }
    "ci-keyvault-officer" = { scope = azurerm_key_vault.main.id, role = "Key Vault Secrets Officer" }
  }

  # key => {principal, scope, role}
  rbac = merge(
    # every app pulls its own image
    { for name in local.services : "${name}-acrpull" => { principal = local.id[name], scope = azurerm_container_registry.main.id, role = "AcrPull" } },
    {
      # Blob Storage: the Session Agent records the audio and keeps the clips; Core saves the
      # parent summary beside the audio; the Scorer only reads the audio; ingestion reads and writes the books.
      "session-agent-audio"  = { principal = local.id["session-agent"], scope = azurerm_storage_container.audio.resource_manager_id, role = "Storage Blob Data Contributor" }
      "session-agent-clips"  = { principal = local.id["session-agent"], scope = azurerm_storage_container.clips.resource_manager_id, role = "Storage Blob Data Contributor" }
      "core-audio"           = { principal = local.id["core"], scope = azurerm_storage_container.audio.resource_manager_id, role = "Storage Blob Data Contributor" }
      "reading-scorer-audio" = { principal = local.id["reading-scorer"], scope = azurerm_storage_container.audio.resource_manager_id, role = "Storage Blob Data Reader" }
      "ingest-books"         = { principal = local.id["ingest"], scope = azurerm_storage_container.books.resource_manager_id, role = "Storage Blob Data Contributor" }

      # Service Bus: who sends to which queue, and who receives (Data Owner on the service's own
      # queue, because KEDA reads its length to wake the app from zero).
      "session-agent-send-core"   = { principal = local.id["session-agent"], scope = local.queue_id["core-events"], role = "Azure Service Bus Data Sender" }
      "session-agent-send-scorer" = { principal = local.id["session-agent"], scope = local.queue_id["scorer-events"], role = "Azure Service Bus Data Sender" }
      "reading-scorer-send-core"  = { principal = local.id["reading-scorer"], scope = local.queue_id["core-events"], role = "Azure Service Bus Data Sender" }
      "core-send-core"            = { principal = local.id["core"], scope = local.queue_id["core-events"], role = "Azure Service Bus Data Sender" }
      "core-receive"              = { principal = local.id["core"], scope = local.queue_id["core-events"], role = "Azure Service Bus Data Owner" }
      "reading-scorer-receive"    = { principal = local.id["reading-scorer"], scope = local.queue_id["scorer-events"], role = "Azure Service Bus Data Owner" }

      # Azure AI: OpenAI for Core (grader, coach, embeddings) and the Scorer (transcript); Speech
      # for the Session Agent (listening), Core (the parent summary, responses) and the Scorer.
      "core-openai"           = { principal = local.id["core"], scope = azurerm_cognitive_account.openai.id, role = "Cognitive Services OpenAI User" }
      "reading-scorer-openai" = { principal = local.id["reading-scorer"], scope = azurerm_cognitive_account.openai.id, role = "Cognitive Services OpenAI User" }
      "ingest-openai"         = { principal = local.id["ingest"], scope = azurerm_cognitive_account.openai.id, role = "Cognitive Services OpenAI User" }
      "session-agent-openai"  = { principal = local.id["session-agent"], scope = azurerm_cognitive_account.openai.id, role = "Cognitive Services OpenAI User" } # the interest tagger
      "session-agent-speech"  = { principal = local.id["session-agent"], scope = azurerm_cognitive_account.speech.id, role = "Cognitive Services Speech User" }
      "core-speech"           = { principal = local.id["core"], scope = azurerm_cognitive_account.speech.id, role = "Cognitive Services Speech User" }
      "reading-scorer-speech" = { principal = local.id["reading-scorer"], scope = azurerm_cognitive_account.speech.id, role = "Cognitive Services Speech User" }

      # Key Vault: only the Account service reads the Paystack secret and the email key; the
      # Account service (which mints LiveKit tokens) and the Session Agent (the worker) read LiveKit's.
      "account-paystack"             = { principal = local.id["account"], scope = azurerm_key_vault_secret.entry["paystack-secret-key"].resource_versionless_id, role = "Key Vault Secrets User" }
      "account-resend"               = { principal = local.id["account"], scope = azurerm_key_vault_secret.entry["resend-api-key"].resource_versionless_id, role = "Key Vault Secrets User" }
      "account-livekit-key"          = { principal = local.id["account"], scope = azurerm_key_vault_secret.entry["livekit-api-key"].resource_versionless_id, role = "Key Vault Secrets User" }
      "account-livekit-secret"       = { principal = local.id["account"], scope = azurerm_key_vault_secret.entry["livekit-api-secret"].resource_versionless_id, role = "Key Vault Secrets User" }
      "session-agent-livekit-key"    = { principal = local.id["session-agent"], scope = azurerm_key_vault_secret.entry["livekit-api-key"].resource_versionless_id, role = "Key Vault Secrets User" }
      "session-agent-livekit-secret" = { principal = local.id["session-agent"], scope = azurerm_key_vault_secret.entry["livekit-api-secret"].resource_versionless_id, role = "Key Vault Secrets User" }
    },
  )
}

resource "azurerm_role_assignment" "ci" {
  for_each             = local.rbac_ci
  principal_id         = azurerm_user_assigned_identity.ci.principal_id
  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "rbac" {
  for_each             = local.rbac
  principal_id         = each.value.principal
  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_type       = "ServicePrincipal"
}

# Cosmos DB's data plane has its own role system. Every service that reads or writes
# documents gets Data Contributor on the one database.
resource "azurerm_cosmosdb_sql_role_assignment" "data" {
  for_each            = local.services
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  role_definition_id  = local.cosmos_data_contributor
  principal_id        = azurerm_user_assigned_identity.svc[each.key].principal_id
  scope               = "${azurerm_cosmosdb_account.main.id}/dbs/${azurerm_cosmosdb_sql_database.main.name}"
}

# ---- budget: alerts at $50, $100 and $130 of the $150 credit

resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "${var.prefix}-budget"
  resource_group_id = azurerm_resource_group.main.id
  amount            = var.budget_amount
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start
  }

  dynamic "notification" {
    for_each = var.budget_alerts
    content {
      enabled        = true
      threshold      = ceil(100 * notification.value / var.budget_amount)
      threshold_type = "Actual"
      operator       = "GreaterThanOrEqualTo"
      contact_emails = var.budget_contact_emails
    }
  }
}
