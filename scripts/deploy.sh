#!/usr/bin/env bash
# Build backend + frontend images, push to Artifact Registry, and apply Terraform.
# Usage: ./scripts/deploy.sh <project_id> <region> <environment>
set -euo pipefail

PROJECT_ID="${1:?Usage: deploy.sh <project_id> <region> <environment>}"
REGION="${2:-europe-west1}"
ENVIRONMENT="${3:-dev}"
REPO="graphrag-platform-${ENVIRONMENT}-images"
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "manual")

BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend:${SHA}"
FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/frontend:${SHA}"

echo "==> Authenticating Docker with Artifact Registry"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "==> Building backend image: ${BACKEND_IMAGE}"
docker build -t "${BACKEND_IMAGE}" ./backend
docker push "${BACKEND_IMAGE}"

echo "==> Building frontend image: ${FRONTEND_IMAGE}"
BACKEND_URL=$(cd terraform && terraform output -raw backend_url 2>/dev/null || echo "")
docker build -t "${FRONTEND_IMAGE}" --build-arg VITE_API_URL="${BACKEND_URL}" ./frontend
docker push "${FRONTEND_IMAGE}"

echo "==> Running Terraform apply"
cd terraform
terraform init -backend-config="bucket=${PROJECT_ID}-graphrag-platform-tfstate" -reconfigure
terraform apply \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="environment=${ENVIRONMENT}" \
  -var="tf_state_bucket_name=${PROJECT_ID}-graphrag-platform-tfstate" \
  -var="container_image_backend=${BACKEND_IMAGE}" \
  -var="container_image_frontend=${FRONTEND_IMAGE}"

echo "==> Done. Backend URL:"
terraform output -raw backend_url
