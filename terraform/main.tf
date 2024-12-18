# Define required roles for infrastructure management
locals {
  infrastructure_roles = toset([
    "roles/secretmanager.admin",
    "roles/container.admin",
    "roles/servicenetworking.networksAdmin",
    "roles/compute.networkAdmin",
    "roles/servicenetworking.serviceAgent"
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
  for_each = {
    database_url        = google_secret_manager_secret.database_url.id
    discord_token       = google_secret_manager_secret.discord_token.id
    discord_client_id   = google_secret_manager_secret.discord_client_id.id
    database_connection = google_secret_manager_secret.database_connection.id
  }

  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.ci_service_account}"
}


# Configure VPC peering for Cloud SQL
# Create VPC network
resource "google_compute_network" "vpc_network" {
  name                    = "vpc-network"
  auto_create_subnetworks = true
}

resource "google_compute_global_address" "private_ip_address" {
  name          = "private-ip-address"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc_network.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network = google_compute_network.vpc_network.id
  service = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}

# Allow GKE pods to access Cloud SQL
resource "google_compute_firewall" "allow_cloudsql_private" {
  name      = "allow-cloudsql-private"
  network   = google_compute_network.vpc_network.name
  direction = "INGRESS"
  priority  = 1000

  source_ranges = ["10.127.0.0/17"]  # GKE pods CIDR range
  target_tags = []  # Empty list means all instances in the network

  allow {
    protocol = "tcp"
    ports = ["5432", "3307"]
  }

  description = "Allow GKE pods to access Cloud SQL"
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "containerregistry.googleapis.com", # Required for GCR
    "sqladmin.googleapis.com", # Required for Cloud SQL
    "secretmanager.googleapis.com", # Required for Secret Manager
    "compute.googleapis.com", # Required for networking operations
    "vpcaccess.googleapis.com", # Required for VPC access
    "container.googleapis.com", # Required for GKE
    "servicenetworking.googleapis.com", # Required for VPC peering
  ])

  service            = each.key
  disable_on_destroy = false
}


# Create Cloud SQL instance
resource "google_sql_database_instance" "instance" {
  depends_on = [google_service_networking_connection.private_vpc_connection]
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
      ipv4_enabled = true  # Enable IPv4 for local connections
      ssl_mode        = "ENCRYPTED_ONLY"
      private_network = google_compute_network.vpc_network.id
    }

    location_preference {
      zone = "${var.region}-c"
    }

    deletion_protection_enabled = false
    availability_type           = "ZONAL"
    disk_autoresize             = true
    disk_size                   = 10
    disk_type                   = "PD_SSD"

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
  }

  deletion_protection = true

}

# Create database
resource "google_sql_database" "database" {
  name     = var.service_name
  instance = google_sql_database_instance.instance.name
}

# Create database users and grant permissions
resource "google_sql_user" "iam_user" {
  name = trimsuffix(google_service_account.workload_service_account.email, ".gserviceaccount.com")
  instance = google_sql_database_instance.instance.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

# Create admin user with password
resource "random_password" "db_admin_password" {
  length  = 32
  special = true
}

resource "google_sql_user" "admin_user" {
  name     = "admin"
  instance = google_sql_database_instance.instance.name
  password = random_password.db_admin_password.result
}

# Store admin password in Secret Manager
resource "google_secret_manager_secret" "db_admin_password" {
  secret_id = "db-admin-password"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_admin_password" {
  secret      = google_secret_manager_secret.db_admin_password.id
  secret_data = random_password.db_admin_password.result
}

# Grant necessary database roles to the IAM user
resource "google_project_iam_member" "cloudsql_instance_user" {
  project = var.project_id
  role    = "roles/cloudsql.instanceUser"
  member  = "serviceAccount:${google_service_account.workload_service_account.email}"
}

resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.workload_service_account.email}"
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
  secret_data = "postgresql+asyncpg://${google_sql_user.iam_user.name}@127.0.0.1/${google_sql_database.database.name}"
}

# Store database URL in Secret Manager
resource "google_secret_manager_secret" "admin_database_url" {
  secret_id = "admin-database-url"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "admin_database_url" {
  secret = google_secret_manager_secret.admin_database_url.id
  secret_data = "postgresql://${google_sql_user.admin_user.name}:${urlencode(random_password.db_admin_password.result)}@${google_sql_database_instance.instance.ip_address.0.ip_address}/${google_sql_database.database.name}"
}

# Data sources for reading secrets
data "google_secret_manager_secret_version" "database_url" {
  secret  = google_secret_manager_secret.database_url.id
  version = "latest"
  depends_on = [google_secret_manager_secret_version.database_url]
}

data "google_secret_manager_secret_version" "discord_token" {
  secret  = google_secret_manager_secret.discord_token.id
  version = "latest"
  depends_on = [google_secret_manager_secret_version.discord_token]
}

data "google_secret_manager_secret_version" "discord_client_id" {
  secret  = google_secret_manager_secret.discord_client_id.id
  version = "latest"
  depends_on = [google_secret_manager_secret_version.discord_client_id]
}

data "google_secret_manager_secret_version" "active_container_tag" {
  secret  = google_secret_manager_secret.active_container_tag.id
  version = "latest"
  depends_on = [google_secret_manager_secret_version.active_container_tag]
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
  depends_on = [google_project_service.required_apis]
  name     = "${var.service_name}-cluster"
  location = var.region  # Regional cluster

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
  network    = google_compute_network.vpc_network.name
  subnetwork = google_compute_network.vpc_network.name
}

# Configure Workload Identity for the bot
resource "google_service_account_iam_binding" "workload_identity_binding" {
  depends_on = [google_container_cluster.primary]
  service_account_id = google_service_account.workload_service_account.name
  role               = "roles/iam.workloadIdentityUser"
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[default/bot-sa]"
  ]
}

# Service account for the bot workload
resource "google_service_account" "workload_service_account" {
  account_id   = "${var.service_name}-workload"
  display_name = "Workload Service Account for ${var.service_name}"
}

# Grant necessary permissions to the bot workload service account
resource "google_project_iam_member" "workload_permissions" {
  for_each = toset([
    "roles/secretmanager.secretAccessor",
    "roles/cloudsql.editor",
    "roles/artifactregistry.reader"  # For accessing Container Registry
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.workload_service_account.email}"
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
