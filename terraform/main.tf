# Grant Secret Manager access to Terraform service account
resource "google_project_iam_member" "terraform_secretmanager_access" {
  project = var.project_id
  role    = "roles/secretmanager.admin"
  member  = "serviceAccount:${var.terraform_service_account}"
}

# Configure Container Registry storage bucket
resource "google_storage_bucket" "registry_bucket" {
  name     = "artifacts.gcr.io"
  location = "US"
  project  = var.project_id
  uniform_bucket_level_access = true
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "containerregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com"
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
      enabled = true
    }
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
    "postgresql://${google_sql_user.user.name}:${random_password.db_password.result}@${google_sql_database_instance.instance.connection_name}/${google_sql_database.database.name}",
    "%",
    "%%"
  )
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

# Allow Terraform service account to read secrets
resource "google_secret_manager_secret_iam_member" "terraform_secret_access" {
  for_each = toset([
    google_secret_manager_secret.database_url.id,
    google_secret_manager_secret.discord_token.id,
    google_secret_manager_secret.discord_client_id.id,
  ])

  secret_id = each.key
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.terraform_service_account}"
}

# Create service account for Cloud Run
resource "google_service_account" "cloud_run_service_account" {
  account_id   = "${var.service_name}-sa"
  display_name = "Service Account for ${var.service_name}"
}

# Grant necessary permissions
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run_service_account.email}"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "default" {
  name     = var.service_name
  location = var.region

  template {
    scaling {
      max_instance_count = 1
    }

    containers {
      # Use a minimal placeholder image for initial deployment
      image = "gcr.io/cloudrun/hello"
      
      startup_probe {
        failure_threshold = 1
        period_seconds   = 240
        timeout_seconds  = 240
        tcp_socket {
          port = 8080
        }
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "DISCORD_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.discord_token.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "DISCORD_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.discord_client_id.secret_id
            version = "latest"
          }
        }
      }
    }

    service_account = google_service_account.cloud_run_service_account.email
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      template[0].revision
    ]
  }
}
