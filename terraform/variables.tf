variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The default GCP region"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
  default     = "nexari"
}

variable "database_instance_tier" {
  description = "The machine type for the database instance"
  type        = string
  default     = "db-f1-micro"
}

variable "discord_token" {
  description = "Discord Bot Token"
  type        = string
  sensitive   = true
}

variable "discord_client_id" {
  description = "Discord Client ID"
  type        = string
  sensitive   = true
}

variable "terraform_service_account" {
  description = "The service account email used by Terraform"
  type        = string
}

variable "ci_service_account" {
  description = "The service account email used by CI/CD pipeline"
  type        = string
}

