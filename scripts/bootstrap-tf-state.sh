#!/usr/bin/env bash
# One-time bootstrap: create the Terraform state bucket and grant the deployer SA access.
# Run this before the first CI deploy if terraform init fails with storage.objects.list 403.
set -euo pipefail

PROJECT_ID="${1:?Usage: bootstrap-tf-state.sh <project_id> [region] [environment]}"
REGION="${2:-europe-west1}"
ENVIRONMENT="${3:-dev}"
BUCKET="${PROJECT_ID}-graphrag-platform-tfstate"
DEPLOYER_SA="graphrag-platform-${ENVIRONMENT}-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud storage buckets describe "gs://${BUCKET}" &>/dev/null; then
  echo "==> Creating state bucket gs://${BUCKET}"
  gcloud storage buckets create "gs://${BUCKET}" --location="${REGION}" --uniform-bucket-level-access
else
  echo "==> Bucket gs://${BUCKET} already exists"
fi

echo "==> Granting storage.objectAdmin to ${DEPLOYER_SA}"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/storage.objectAdmin"

echo "==> Done. Set GitHub secret TF_STATE_BUCKET=${BUCKET}"
