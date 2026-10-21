output "resource_group" {
  value = azurerm_resource_group.main.name
}

output "acr_login_server" {
  description = "CI pushes images here and passes their digests back as var.images."
  value       = azurerm_container_registry.main.login_server
}

output "ci_client_id" {
  description = "Client id of the CI deployer identity (the GitHub variable AZURE_CLIENT_ID)."
  value       = azurerm_user_assigned_identity.ci.client_id
}

output "tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}

output "subscription_id" {
  value = data.azurerm_client_config.current.subscription_id
}

output "account_url" {
  description = "The Account service's public URL: the web app's API, the Paystack webhook, and the Core service's /internal/notify."
  value       = "https://${azurerm_container_app.account.ingress[0].fqdn}"
}

output "core_internal_url" {
  value = "https://${azurerm_container_app.core.ingress[0].fqdn}"
}

output "clips_base_url" {
  description = "CLIPS_BASE_URL: what the browser fetches clips from."
  value       = "${azurerm_storage_account.main.primary_blob_endpoint}${azurerm_storage_container.clips.name}"
}

output "key_vault" {
  description = "Set the secret values here (README.md)."
  value       = azurerm_key_vault.main.name
}

output "openai_deployments" {
  description = "AZURE_OPENAI_DEPLOYMENTS: role -> deployment name."
  value       = local.deployment_names
}

output "servicebus_queues" {
  value = sort(tolist(local.queues))
}

output "web_url" {
  description = "The web app's address. Register web_redirect_uri as the single-page-app redirect URI of the Entra app registration (README.md)."
  value       = "https://${azurerm_static_web_app.web.default_host_name}"
}

output "web_redirect_uri" {
  value = "https://${azurerm_static_web_app.web.default_host_name}/signin"
}

output "web_app_name" {
  description = "The Static Web Apps resource CI deploys to."
  value       = azurerm_static_web_app.web.name
}

output "jobs" {
  description = "Run with: az containerapp job start --name <job> --resource-group <resource_group>. seed makes the clips and writes the bank passages; book_ingest embeds the catalogue."
  value = {
    seed        = azurerm_container_app_job.seed.name
    book_ingest = azurerm_container_app_job.book_ingest.name
  }
}
