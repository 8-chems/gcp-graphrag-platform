terraform {
  required_version = ">= 1.7.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "gcs" {
    # bucket set via -backend-config="bucket=YOUR_TF_STATE_BUCKET"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  name_prefix         = "${var.app_name}-${var.environment}"
  tf_state_bucket     = var.tf_state_bucket_name != "" ? var.tf_state_bucket_name : "${var.project_id}-${var.app_name}-tfstate"
  firebase_project_id = var.firebase_project_id != "" ? var.firebase_project_id : var.project_id
  labels = {
    app         = var.app_name
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "firebase.googleapis.com",
    "identitytoolkit.googleapis.com",
    "vpcaccess.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}
