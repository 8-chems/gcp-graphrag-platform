resource "google_bigquery_dataset" "graphrag" {
  dataset_id = "graphrag"
  location   = var.region

  description = "Stores document chunk embeddings for semantic (vector) search"

  labels = local.labels

  access {
    role          = "OWNER"
    user_by_email = google_service_account.backend_sa.email
  }

  access {
    role          = "OWNER"
    special_group = "projectOwners"
  }
}

resource "google_bigquery_table" "document_embeddings" {
  dataset_id = google_bigquery_dataset.graphrag.dataset_id
  table_id   = "document_embeddings"

  deletion_protection = false

  schema = jsonencode([
    { name = "chunk_id", type = "STRING", mode = "REQUIRED" },
    { name = "document_id", type = "STRING", mode = "REQUIRED" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "content", type = "STRING", mode = "NULLABLE" },
    { name = "embedding", type = "FLOAT64", mode = "REPEATED" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}
