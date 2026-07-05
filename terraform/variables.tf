variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Primary GCP region"
  type        = string
  default     = "europe-west1"
}

variable "environment" {
  description = "Deployment environment (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "app_name" {
  description = "Base name used for resource naming"
  type        = string
  default     = "graphrag-platform"
}

variable "sql_tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-custom-2-7680"
}

variable "sql_database_version" {
  type    = string
  default = "POSTGRES_15"
}

variable "neo4j_uri" {
  description = "Neo4j AuraDB (or self-hosted) bolt URI, injected as a secret"
  type        = string
  sensitive   = true
}

variable "neo4j_user" {
  type      = string
  sensitive = true
}

variable "neo4j_password" {
  type      = string
  sensitive = true
}

variable "container_image_backend" {
  description = "Fully qualified backend image, e.g. europe-west1-docker.pkg.dev/PROJECT/repo/backend:tag"
  type        = string
  default     = ""
}

variable "container_image_frontend" {
  description = "Fully qualified frontend image"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "owner/repo for Workload Identity Federation binding"
  type        = string
  default     = ""
}

variable "admin_emails" {
  description = "Comma-separated bootstrap admin allowlist (fallback until Firebase custom claims are set via scripts/set_admin_claim.py)"
  type        = string
  default     = ""
}

variable "tf_state_bucket_name" {
  description = "GCS bucket for Terraform remote state (bootstrap bucket, created before first init)"
  type        = string
  default     = ""
}

variable "firebase_project_id" {
  description = "Firebase project ID (from Firebase console; often differs from GCP project_id)"
  type        = string
  default     = ""
}

variable "gemini_model" {
  description = "Vertex AI Gemini model ID (must be available in var.region)"
  type        = string
  default     = "gemini-2.5-flash"
}
