output "backend_url" {
  value = google_cloud_run_v2_service.backend.uri
}

output "frontend_url" {
  value = google_cloud_run_v2_service.frontend.uri
}

output "sql_instance_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "documents_bucket" {
  value = google_storage_bucket.documents.name
}

output "artifact_registry_repo" {
  value = google_artifact_registry_repository.images.name
}

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github_provider.name
}

output "deployer_service_account" {
  value = google_service_account.deployer_sa.email
}
