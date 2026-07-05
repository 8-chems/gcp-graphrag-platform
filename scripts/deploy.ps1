# Build backend + frontend images, push to Artifact Registry, and apply Terraform.
# Usage: .\scripts\deploy.ps1 -ProjectId "your-project" -Region "europe-west1" -Environment "dev"
param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [string]$Region = "europe-west1",
    [string]$Environment = "dev"
)

$ErrorActionPreference = "Stop"

$Repo = "graphrag-platform-$Environment-images"
try {
    $Sha = (git rev-parse --short HEAD) 2>$null
    if (-not $Sha) { $Sha = "manual" }
} catch {
    $Sha = "manual"
}

$BackendImage  = "$Region-docker.pkg.dev/$ProjectId/$Repo/backend:$Sha"
$FrontendImage = "$Region-docker.pkg.dev/$ProjectId/$Repo/frontend:$Sha"

Write-Host "==> Authenticating Docker with Artifact Registry"
gcloud auth configure-docker "$Region-docker.pkg.dev" --quiet

Write-Host "==> Building backend image: $BackendImage"
docker build -t $BackendImage ./backend
docker push $BackendImage

Write-Host "==> Building frontend image: $FrontendImage"
Push-Location terraform
$BackendUrl = ""
try { $BackendUrl = (terraform output -raw backend_url) } catch { $BackendUrl = "" }
Pop-Location
$FirebaseAuthDomain = if ($env:FIREBASE_AUTH_DOMAIN) { $env:FIREBASE_AUTH_DOMAIN } else { "$ProjectId.firebaseapp.com" }
if (-not $env:FIREBASE_API_KEY) { throw "Set FIREBASE_API_KEY (Firebase console -> Project settings -> Web API key)" }
docker build -t $FrontendImage `
  --build-arg VITE_API_URL=$BackendUrl `
  --build-arg VITE_FIREBASE_API_KEY=$env:FIREBASE_API_KEY `
  --build-arg VITE_FIREBASE_AUTH_DOMAIN=$FirebaseAuthDomain `
  --build-arg VITE_FIREBASE_PROJECT_ID=$ProjectId `
  ./frontend
docker push $FrontendImage

Write-Host "==> Running Terraform apply"
Push-Location terraform
terraform init -backend-config="bucket=$ProjectId-graphrag-platform-tfstate" -reconfigure
terraform apply `
  -var="project_id=$ProjectId" `
  -var="region=$Region" `
  -var="environment=$Environment" `
  -var="tf_state_bucket_name=$ProjectId-graphrag-platform-tfstate" `
  -var="container_image_backend=$BackendImage" `
  -var="container_image_frontend=$FrontendImage"

Write-Host "==> Done. Backend URL:"
terraform output -raw backend_url
Pop-Location
