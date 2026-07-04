# Neo4j credentials (Aura or self-hosted) are supplied as Terraform variables
# (via -var or a *.tfvars file that is NOT committed) and stored in Secret Manager,
# then mounted as env vars into the Cloud Run service.

resource "google_secret_manager_secret" "neo4j_uri" {
  secret_id = "${local.name_prefix}-neo4j-uri"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "neo4j_uri" {
  secret      = google_secret_manager_secret.neo4j_uri.id
  secret_data = var.neo4j_uri
}

resource "google_secret_manager_secret" "neo4j_user" {
  secret_id = "${local.name_prefix}-neo4j-user"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "neo4j_user" {
  secret      = google_secret_manager_secret.neo4j_user.id
  secret_data = var.neo4j_user
}

resource "google_secret_manager_secret" "neo4j_password" {
  secret_id = "${local.name_prefix}-neo4j-password"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "neo4j_password" {
  secret      = google_secret_manager_secret.neo4j_password.id
  secret_data = var.neo4j_password
}
