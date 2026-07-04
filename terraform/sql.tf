resource "google_sql_database_instance" "postgres" {
  name             = "${local.name_prefix}-pg"
  database_version = var.sql_database_version
  region           = var.region

  settings {
    tier              = var.sql_tier
    availability_type = var.environment == "prod" ? "REGIONAL" : "ZONAL"
    disk_autoresize   = true
    disk_size         = 20

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = var.environment == "prod"
    }

    ip_configuration {
      ipv4_enabled = true
      # For production, prefer private IP + VPC peering instead of public IP.
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
  }

  deletion_protection = var.environment == "prod"

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "app_db" {
  name     = "app_db"
  instance = google_sql_database_instance.postgres.name
}

resource "random_password" "sql_password" {
  length  = 24
  special = false
}

resource "google_sql_user" "app_user" {
  name     = "app_user"
  instance = google_sql_database_instance.postgres.name
  password = random_password.sql_password.result
}

resource "google_secret_manager_secret" "sql_password" {
  secret_id = "${local.name_prefix}-sql-password"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "sql_password" {
  secret      = google_secret_manager_secret.sql_password.id
  secret_data = random_password.sql_password.result
}
