<#
.SYNOPSIS
  One-time preparation of the Google Cloud project for ArchitectureScope.
.DESCRIPTION
  Turns on the Google services the app uses (Cloud Run, Cloud Build,
  Artifact Registry, Secret Manager) and lets Cloud Run's robot account
  build the app and read its secrets. Safe to run again.
  Deployment Guide, Step 8.
.EXAMPLE
  .\deploy\setup-project.ps1
#>
param(
    # Defaults to the project chosen with `gcloud config set project`.
    [string]$Project = ""
)

function Fail([string]$message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Red
    exit 1
}

if (-not $Project) { $Project = (& gcloud config get-value project 2>$null) }
if (-not $Project) { Fail "No project selected. Run: gcloud config set project YOUR_PROJECT_ID" }
Write-Host "Project: $Project" -ForegroundColor Cyan

Write-Host "`n1/3  Turning on Cloud Run, Cloud Build, Artifact Registry and Secret Manager (1-3 minutes)..." -ForegroundColor Cyan
& gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com `
    secretmanager.googleapis.com compute.googleapis.com --project $Project
if ($LASTEXITCODE -ne 0) { Fail "Could not turn the services on. Is billing linked to the project? (Guide, Step 1)" }

$number = (& gcloud projects describe $Project --format="value(projectNumber)")
if ($LASTEXITCODE -ne 0 -or -not $number) { Fail "Could not read the project number." }
$robot = "serviceAccount:$number-compute@developer.gserviceaccount.com"

Write-Host "`n2/3  Letting Cloud Run read the app's secrets..." -ForegroundColor Cyan
& gcloud projects add-iam-policy-binding $Project --member=$robot --role="roles/secretmanager.secretAccessor" `
    --condition=None --quiet | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "Could not grant the secret permission." }

Write-Host "`n3/3  Letting Cloud Build build the app..." -ForegroundColor Cyan
& gcloud projects add-iam-policy-binding $Project --member=$robot --role="roles/run.builder" `
    --condition=None --quiet | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "Could not grant the build permission." }

Write-Host "`nDone. Project $Project (number $number) is ready." -ForegroundColor Green
