resource "google_vpc_access_connector" "connector" {
  name          = "gr-vpc-${var.environment}"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = "default"
}

resource "google_cloud_run_v2_service" "backend" {
  name     = "${local.name_prefix}-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.backend_sa.email

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    scaling {
      min_instance_count = var.environment == "prod" ? 1 : 0
      max_instance_count = 10
    }

    containers {
      image = var.container_image_backend != "" ? var.container_image_backend : "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "FIREBASE_PROJECT_ID"
        value = local.firebase_project_id
      }
      env {
        name  = "REGION"
        value = var.region
      }
      env {
        name  = "SQL_INSTANCE_CONNECTION_NAME"
        value = google_sql_database_instance.postgres.connection_name
      }
      env {
        name  = "SQL_HOST"
        value = "/cloudsql/${google_sql_database_instance.postgres.connection_name}"
      }
      env {
        name  = "SQL_USER"
        value = google_sql_user.app_user.name
      }
      env {
        name = "SQL_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.sql_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.documents.name
      }
      env {
        name  = "ADMIN_EMAILS"
        value = var.admin_emails
      }
      env {
        name = "NEO4J_URI"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.neo4j_uri.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "NEO4J_USER"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.neo4j_user.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "NEO4J_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.neo4j_password.secret_id
            version = "latest"
          }
        }
      }

      ports {
        container_port = 8080
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  name     = google_cloud_run_v2_service.backend.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service" "frontend" {
  name     = "${local.name_prefix}-frontend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = var.container_image_frontend != "" ? var.container_image_frontend : "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      ports {
        container_port = 8080
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  name     = google_cloud_run_v2_service.frontend.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
