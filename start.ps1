#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start Aurora in native dev mode: Postgres+Redis via Docker, backend
    (uvicorn) and frontend (Vite) each in their own window so their logs
    stay visible and Ctrl+C in either stops just that process.
#>

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

if (-not (Test-Path (Join-Path $RepoRoot ".env"))) {
    Write-Host "No .env found -- copying .env.example. Edit it (AI provider keys, etc.) before continuing." -ForegroundColor Yellow
    Copy-Item (Join-Path $RepoRoot ".env.example") (Join-Path $RepoRoot ".env")
}

if (-not (Test-Path (Join-Path $RepoRoot "backend\.venv"))) {
    Write-Host "backend\.venv not found. Run this first:" -ForegroundColor Red
    Write-Host "  cd backend; python -m venv .venv; .venv\Scripts\activate; pip install -r requirements.txt"
    exit 1
}

if (-not (Test-Path (Join-Path $RepoRoot "frontend\node_modules"))) {
    Write-Host "frontend\node_modules not found. Run this first:" -ForegroundColor Red
    Write-Host "  cd frontend; npm install"
    exit 1
}

$dockerAvailable = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)
if ($dockerAvailable) {
    Write-Host "Starting Postgres + Redis via Docker Compose..." -ForegroundColor Cyan
    Push-Location $RepoRoot
    docker compose up -d postgres redis
    Pop-Location
} else {
    Write-Host "Docker not found -- make sure Postgres (with pgvector) and Redis are running natively (see README.md)." -ForegroundColor Yellow
}

Write-Host "Starting backend (uvicorn) on http://localhost:8000 ..." -ForegroundColor Cyan
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$RepoRoot\backend'; .venv\Scripts\activate; uvicorn app.main:app --reload"

Write-Host "Starting frontend (Vite) on http://localhost:5173 ..." -ForegroundColor Cyan
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$RepoRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "Aurora is starting in two new windows. Close either window (or Ctrl+C inside it) to stop that service." -ForegroundColor Green
