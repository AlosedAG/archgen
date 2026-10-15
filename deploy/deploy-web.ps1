<#
.SYNOPSIS
  Deploy (or update) the ArchitectureScope web app on Google Cloud Run.
.DESCRIPTION
  The web app needs the API's address when it is built. The first time, this
  script reads it from the deployed "archscope-api" service and writes
  apps/web/.env.production (API_URL=...). Then it uploads apps/web, has
  Cloud Build build apps/web/Dockerfile, and runs it as "archscope-web".
  Deployment Guide, Step 14.
.EXAMPLE
  .\deploy\deploy-web.ps1
#>
param(
    [string]$Region = "us-central1",
    [string]$Service = "archscope-web",
    [string]$ApiService = "archscope-api"
)

function Fail([string]$message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Red
    exit 1
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$envProduction = Join-Path $root "apps\web\.env.production"

if (-not (Test-Path $envProduction)) {
    $api = (& gcloud run services describe $ApiService --region $Region --format="value(status.url)" 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $api) { Fail "The API isn't deployed yet. Run .\deploy\deploy-api.ps1 first (Guide, Step 12)." }
    # UTF-8 without a byte-order mark, so the build can read it.
    [IO.File]::WriteAllText($envProduction, "API_URL=$api`n")
    Write-Host "Created apps\web\.env.production -> API_URL=$api" -ForegroundColor Cyan
}
if ((Get-Content $envProduction -Raw) -notmatch '(?m)^API_URL=https://\S+[^/\s]\s*$') {
    Fail "apps\web\.env.production must be one line: API_URL=https://archscope-api-....run.app (no slash at the end)."
}

Write-Host "Deploying $Service to $Region. This takes 5-8 minutes...`n" -ForegroundColor Cyan
& gcloud run deploy $Service `
    --source apps/web `
    --region $Region `
    --allow-unauthenticated `
    --memory 512Mi --cpu 1 `
    --min-instances 0 --max-instances 2 `
    --timeout 300
if ($LASTEXITCODE -ne 0) { Fail "The deploy failed. Read the message above, then the Troubleshooting table in the guide." }

$url = (& gcloud run services describe $Service --region $Region --format="value(status.url)")
Write-Host "`nArchitectureScope is live at:  $url" -ForegroundColor Green
Write-Host "This is the link to share with your team." -ForegroundColor Green
