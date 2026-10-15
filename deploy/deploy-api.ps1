<#
.SYNOPSIS
  Deploy (or update) the ArchitectureScope API on Google Cloud Run.
.DESCRIPTION
  Uploads the project folder (minus what .gcloudignore leaves out), has
  Cloud Build build the root Dockerfile, and runs it as the Cloud Run service
  "archscope-api". Plain settings come from deploy/cloudrun-api.env.yaml,
  private ones from Secret Manager. Email is switched on automatically when
  the "archscope-smtp-password" secret exists. Deployment Guide, Step 12.
.EXAMPLE
  .\deploy\deploy-api.ps1
#>
param(
    [string]$Region = "us-central1",
    [string]$Service = "archscope-api"
)

function Fail([string]$message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Red
    exit 1
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$envFile = Join-Path $PSScriptRoot "cloudrun-api.env.yaml"
$secrets = "ARCHSCOPE_DATABASE_URL=archscope-database-url:latest,ARCHSCOPE_SECRET_KEY=archscope-secret-key:latest"

foreach ($name in "archscope-database-url", "archscope-secret-key") {
    $null = & gcloud secrets describe $name --format="value(name)" 2>&1
    if ($LASTEXITCODE -ne 0) { Fail "Secret '$name' was not found in Secret Manager. Create it first (Guide, Step 11)." }
}

$null = & gcloud secrets describe archscope-smtp-password --format="value(name)" 2>&1
if ($LASTEXITCODE -eq 0) {
    $settings = Get-Content $envFile -Raw
    if ($settings -notmatch '(?m)^ARCHSCOPE_SMTP_USERNAME:\s*"[^"\s]+@[^"\s]+"') {
        Fail "Email is set up (secret 'archscope-smtp-password' exists), but ARCHSCOPE_SMTP_USERNAME in deploy\cloudrun-api.env.yaml is empty. Put the Gmail address between the quotes, save, and run this again."
    }
    $secrets += ",ARCHSCOPE_SMTP_PASSWORD=archscope-smtp-password:latest"
    Write-Host "Email: on (Gmail)" -ForegroundColor Cyan
} else {
    Write-Host "Email: off (no 'archscope-smtp-password' secret) - accounts are created from the laptop." -ForegroundColor Cyan
}

Write-Host "Deploying $Service to $Region. The first time takes 5-10 minutes...`n" -ForegroundColor Cyan
& gcloud run deploy $Service `
    --source . `
    --region $Region `
    --allow-unauthenticated `
    --memory 1Gi --cpu 1 `
    --min-instances 0 --max-instances 2 `
    --timeout 300 `
    --env-vars-file $envFile `
    --set-secrets $secrets
if ($LASTEXITCODE -ne 0) { Fail "The deploy failed. Read the message above, then the Troubleshooting table in the guide." }

$url = (& gcloud run services describe $Service --region $Region --format="value(status.url)")
Write-Host "`nThe API is live at:  $url" -ForegroundColor Green
Write-Host "Check it in your browser:  $url/healthz" -ForegroundColor Green
