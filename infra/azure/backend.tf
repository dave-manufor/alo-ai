# State lives in Blob Storage, in the EU, with versioning on. The storage account is created
# once by hand with the CI deployer identity (see README.md); everything else is Terraform.
terraform {
  backend "azurerm" {
    resource_group_name  = "aloai-tfstate-rg"
    storage_account_name = "aloaitfstateeu"
    container_name       = "tfstate"
    key                  = "aloai-azure.tfstate"
    use_azuread_auth     = true
  }
}
