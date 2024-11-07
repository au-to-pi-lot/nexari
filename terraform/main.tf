# Define required roles for infrastructure management
locals {
  infrastructure_roles = toset([
    "roles/secretmanager.admin",
    "roles/container.admin"
  ])
}

# Grant permissions to CI service account
resource "google_project_iam_member" "ci_permissions" {
  for_each = local.infrastructure_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.ci_service_account}"
}

# Allow CI service account to read secrets
resource "google_secret_manager_secret_iam_member" "ci_secret_access" {
  for_each = toset([
    google_secret_manager_secret.database_url.id,
    google_secret_manager_secret.discord_token.id,
    google_secret_manager_secret.discord_client_id.id,
    google_secret_manager_secret.database_connection.id,
  ])

  secret_id = each.key
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.ci_service_account}"
}


# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "containerregistry.googleapis.com", # Required for GCR
    "sqladmin.googleapis.com", # Required for Cloud SQL
    "secretmanager.googleapis.com", # Required for Secret Manager
    "compute.googleapis.com", # Required for networking operations

  ])

  service            = each.key
  disable_on_destroy = false
}


# Create Cloud SQL instance
resource "google_sql_database_instance" "instance" {
  name             = "${var.service_name}-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = var.database_instance_tier

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = false
      start_time                     = "04:00"
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled = false
      require_ssl  = true
    }

    location_preference {
      zone = "${var.region}-c"
    }

    deletion_protection_enabled = false
    availability_type           = "ZONAL"
    disk_autoresize             = true
    disk_size                   = 10
    disk_type                   = "PD_SSD"
  }

  deletion_protection = true

}

# Create database
resource "google_sql_database" "database" {
  name     = var.service_name
  instance = google_sql_database_instance.instance.name
}

# Create database user
resource "google_sql_user" "user" {
  name     = var.service_name
  instance = google_sql_database_instance.instance.name
  password = random_password.db_password.result
}

# Get current client config
data "google_client_config" "current" {}

# Store database URL in Secret Manager
resource "google_secret_manager_secret" "database_url" {
  secret_id = "database-url"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id
  secret_data = replace(
    "postgresql+asyncpg://${google_sql_user.user.name}:${random_password.db_password.result}@127.0.0.1/${google_sql_database.database.name}",
    "%",
    "%%"
  )
}

# Data sources for reading secrets
data "google_secret_manager_secret_version" "database_url" {
  secret  = google_secret_manager_secret.database_url.id
  version = "latest"
}

data "google_secret_manager_secret_version" "discord_token" {
  secret  = google_secret_manager_secret.discord_token.id
  version = "latest"
}

data "google_secret_manager_secret_version" "discord_client_id" {
  secret  = google_secret_manager_secret.discord_client_id.id
  version = "latest"
}

data "google_secret_manager_secret_version" "active_container_tag" {
  secret  = google_secret_manager_secret.active_container_tag.id
  version = "latest"
}

# Generate random database password
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Create Secret Manager secrets
resource "google_secret_manager_secret" "discord_token" {
  secret_id = "discord-token"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "discord_token" {
  secret      = google_secret_manager_secret.discord_token.id
  secret_data = var.discord_token
}

resource "google_secret_manager_secret" "discord_client_id" {
  secret_id = "discord-client-id"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "discord_client_id" {
  secret      = google_secret_manager_secret.discord_client_id.id
  secret_data = var.discord_client_id
}


# Create GKE Autopilot cluster
resource "google_container_cluster" "primary" {
  name     = "${var.service_name}-cluster"
  location = "${var.region}-c"  # Zonal cluster

  # Enable Autopilot mode
  enable_autopilot = true

  # Use release channel for auto-upgrades
  release_channel {
    channel = "REGULAR"
  }

  # Workload Identity configuration
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Network configuration
  network    = "default"
  subnetwork = "default"

  # Enable network policy
  network_policy {
    enabled = true
    provider = "CALICO"
  }
}

# Configure Workload Identity for the bot
resource "google_service_account_iam_binding" "workload_identity_binding" {
  service_account_id = google_service_account.bot_service_account.name
  role               = "roles/iam.workloadIdentityUser"
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[default/bot-sa]"
  ]
}

# Rename service account for GCE
resource "google_service_account" "bot_service_account" {
  account_id   = "${var.service_name}-sa"
  display_name = "Service Account for ${var.service_name}"
}

# Grant necessary permissions to the bot service account
resource "google_project_iam_member" "bot_permissions" {
  for_each = toset([
    "roles/secretmanager.secretAccessor",
    "roles/cloudsql.client",
    "roles/artifactregistry.reader"  # For accessing Container Registry
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.bot_service_account.email}"
}

# Store Cloud SQL connection name in Secret Manager
resource "google_secret_manager_secret" "database_connection" {
  secret_id = "database-connection"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_connection" {
  secret      = google_secret_manager_secret.database_connection.id
  secret_data = google_sql_database_instance.instance.connection_name
}

# Secret to store current active container tag
resource "google_secret_manager_secret" "active_container_tag" {
  secret_id = "active-container-tag"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "active_container_tag" {
  secret      = google_secret_manager_secret.active_container_tag.id
  secret_data = "latest"  # Default to latest
}
