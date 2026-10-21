terraform {
  required_version = "~> 1.13"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 4.81.0"
    }
    # The books container needs a vector index, which azurerm cannot express yet.
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.0"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = false
    }
  }
  # Entra ID for the data plane too: no storage keys, no Cosmos keys.
  storage_use_azuread = true
}

provider "azapi" {}
