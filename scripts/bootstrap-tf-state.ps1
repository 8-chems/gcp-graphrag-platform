# One-time bootstrap: create the Terraform state bucket and grant the deployer SA access.
# Usage: .\scripts\bootstrap-tf-state.ps1 -ProjectId "your-project"
param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [string]$Region = "europe-west1",
    [string]$Environment = "dev"
)

$ErrorActionPreference = "Stop"

$Bucket = "$ProjectId-graphrag-platform-tfstate"
$DeployerSa = "graphrag-platform-$Environment-deployer@$ProjectId.iam.gserviceaccount.com"

$exists = $false
try {
    gcloud storage buckets describe "gs://$Bucket" 2>$null | Out-Null
    $exists = $true
} catch {}

if (-not $exists) {
    Write-Host "==> Creating state bucket gs://$Bucket"
    gcloud storage buckets create "gs://$Bucket" --location=$Region --uniform-bucket-level-access
} else {
    Write-Host "==> Bucket gs://$Bucket already exists"
}

Write-Host "==> Granting storage.objectAdmin to $DeployerSa"
gcloud storage buckets add-iam-policy-binding "gs://$Bucket" `
  --member="serviceAccount:$DeployerSa" `
  --role="roles/storage.objectAdmin"

Write-Host "==> Done. Set GitHub secret TF_STATE_BUCKET=$Bucket"
