<#
.SYNOPSIS
    WebCMD Windows One-Click Development & Demo Launcher
.DESCRIPTION
    Checks prerequisites, initializes required directories, starts the local
    test lab server (port 9888), starts the WebCMD web server (port 8000),
    and opens the WebCMD interactive control dashboard in your browser.
#>

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  WebCMD - AI Execution Runtime Launcher (Windows)          " -ForegroundColor White -BackgroundColor DarkBlue
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Prerequisite Verification
Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Yellow

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js is not found on PATH. Please install Node.js (v18+)."
    exit 1
}
$nodeVersion = node -v
Write-Host "  ✓ Node.js found ($nodeVersion)" -ForegroundColor Green

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  ⚠ 'uv' not found on PATH. Falling back to python -m venv..." -ForegroundColor Yellow
    $useUv = $false
} else {
    $uvVersion = uv --version
    Write-Host "  ✓ Astral uv found ($uvVersion)" -ForegroundColor Green
    $useUv = $true
}

# 2. Ensure Data Directories
Write-Host "[2/5] Initializing local storage directories..." -ForegroundColor Yellow
$projectRoot = $PSScriptRoot
$dataDirs = @(
    "$projectRoot\data",
    "$projectRoot\data\browser-profile",
    "$projectRoot\data\downloads",
    "$projectRoot\data\screenshots",
    "$projectRoot\data\artifacts",
    "$projectRoot\data\checkpoints",
    "$projectRoot\data\logs"
)

foreach ($dir in $dataDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "  ✓ Directory structure initialized at ./data/" -ForegroundColor Green

# 3. Start Local Test Lab Portal (Port 9888)
Write-Host "[3/5] Checking local test lab portal (port 9888)..." -ForegroundColor Yellow
$labRunning = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("127.0.0.1", 9888)
    $labRunning = $true
    $tcp.Close()
} catch {
    $labRunning = $false
}

$labProcess = $null
if ($labRunning) {
    Write-Host "  ✓ Local test lab portal is already running on http://127.0.0.1:9888" -ForegroundColor Green
} else {
    Write-Host "  Starting local test lab portal (node test-lab/server.mjs)..." -ForegroundColor Cyan
    $labProcess = Start-Process -FilePath "node" -ArgumentList "test-lab/server.mjs" -WorkingDirectory $projectRoot -PassThru -NoNewWindow
    Start-Sleep -Seconds 1
    Write-Host "  ✓ Test lab portal started (PID: $($labProcess.Id))" -ForegroundColor Green
}

# 4. Open Browser Dashboard
Write-Host "[4/5] Launching WebCMD Dashboard..." -ForegroundColor Yellow
Start-Process "http://127.0.0.1:8000"

# 5. Start WebCMD Orchestrator Server
Write-Host "[5/5] Starting WebCMD Web Server on http://127.0.0.1:8000..." -ForegroundColor Yellow
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to stop all WebCMD services." -ForegroundColor Magenta
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray

$orchestratorDir = Join-Path $projectRoot "python_orchestrator"
try {
    if ($useUv) {
        & uv run --directory $orchestratorDir webcmd web --port 8000
    } else {
        Set-Location $orchestratorDir
        & python -m webcmd web --port 8000
    }
} finally {
    if ($labProcess -and -not $labProcess.HasExited) {
        Write-Host "`nStopping local test lab portal (PID: $($labProcess.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $labProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "WebCMD shutdown complete." -ForegroundColor Cyan
}
