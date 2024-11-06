# Define required roles for infrastructure management
locals {
  infrastructure_roles = toset([
    "roles/secretmanager.admin",
    "roles/compute.admin",
    "roles/compute.networkUser"
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
      ipv4_enabled = true
      authorized_networks {
        name  = "allow-bot-instance"
        value = google_compute_address.static_ip.address
      }
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
    "postgresql+asyncpg://${google_sql_user.user.name}:${random_password.db_password.result}@${google_sql_database_instance.instance.public_ip_address}/${google_sql_database.database.name}",
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


# Create static IP address
resource "google_compute_address" "static_ip" {
  name   = "${var.service_name}-static-ip"
  region = var.region
}

# Create GCE instance
resource "google_compute_instance" "bot" {
  name         = var.service_name
  machine_type = var.machine_type
  zone         = "${var.region}-c"

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 20
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.static_ip.address
    }
  }

  # Allow instance to access cloud APIs
  service_account {
    email = google_service_account.bot_service_account.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = templatefile("${path.module}/startup-script.tpl", {
      project_id           = var.project_id
      region               = var.region
      service_name         = var.service_name
      database_url         = data.google_secret_manager_secret_version.database_url.secret_data
      discord_token        = data.google_secret_manager_secret_version.discord_token.secret_data
      discord_client_id    = data.google_secret_manager_secret_version.discord_client_id.secret_data
      active_container_tag = data.google_secret_manager_secret_version.active_container_tag.secret_data
    })

  allow_stopping_for_update = true
}

# Rename service account for GCE
resource "google_service_account" "bot_service_account" {
  account_id   = "${var.service_name}-sa"
  display_name = "Service Account for ${var.service_name}"
}

# Grant necessary permissions to the VM service account
resource "google_project_iam_member" "vm_permissions" {
  for_each = toset([
    "roles/secretmanager.secretAccessor",
    "roles/cloudsql.client",
    "roles/storage.objectViewer"  # For accessing Container Registry
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.bot_service_account.email}"
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
