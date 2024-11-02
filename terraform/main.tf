# Grant necessary permissions to Terraform service account
resource "google_project_iam_member" "terraform_permissions" {
  for_each = toset([
    "roles/secretmanager.admin",
    "roles/servicenetworking.networksAdmin",
    "roles/compute.networkAdmin",
    "roles/servicenetworking.serviceAgent"
  ])
  
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${var.terraform_service_account}"
}

# Enable the Service Networking connection
resource "google_project_service_identity" "servicenetworking" {
  provider = google-beta
  project  = var.project_id
  service  = "servicenetworking.googleapis.com"
}

# Grant the Service Networking service agent the necessary permissions
resource "google_project_iam_member" "servicenetworking_agent" {
  project = var.project_id
  role    = "roles/servicenetworking.serviceAgent"
  member  = "serviceAccount:${google_project_service_identity.servicenetworking.email}"
}


# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "containerregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
    "compute.googleapis.com"  # Required for VPC and networking operations
  ])

  service            = each.key
  disable_on_destroy = false
}

# Create VPC network
resource "google_compute_network" "vpc" {
  name                    = "${var.service_name}-vpc"
  auto_create_subnetworks = false
}

# Reserve global internal address range for the peering
resource "google_compute_global_address" "private_ip_address" {
  name          = "${var.service_name}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

# Create VPC peering connection
resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}

# Create subnet
resource "google_compute_subnetwork" "subnet" {
  name          = "${var.service_name}-subnet"
  ip_cidr_range = "10.0.0.0/28"
  network       = google_compute_network.vpc.id
  region        = var.region
}

# Create VPC connector
resource "google_vpc_access_connector" "connector" {
  name          = "${var.service_name}-vpc-connector"
  subnet {
    name = google_compute_subnetwork.subnet.name
  }
  machine_type = "e2-micro"
  min_instances = 2
  max_instances = 3
  region        = var.region
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

    ip_configuration {
      ipv4_enabled    = true
      private_network = google_compute_network.vpc.id
    }
  }

  deletion_protection = true

  depends_on = [
    google_compute_network.vpc,
    google_service_networking_connection.private_vpc_connection
  ]
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
    "postgresql+asyncpg://${google_sql_user.user.name}:${random_password.db_password.result}@${google_sql_database_instance.instance.ip_address.0.ip_address}:5432/${google_sql_database.database.name}",
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

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress = "ALL_TRAFFIC"
    }

    containers {
      # Use a minimal placeholder image for initial deployment
      image = "gcr.io/cloudrun/hello"

      startup_probe {
        initial_delay_seconds = 1
        failure_threshold     = 3
        period_seconds        = 10
        timeout_seconds       = 1
        http_get {
          path = "/"
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
        name = "BOT_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.discord_token.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "CLIENT_ID"
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
      client,
      client_version,
      template[0].containers[0].image,
      template[0].revision,
      template[0].labels.commit-sha,
      template[0].labels.managed-by
    ]
  }
}
